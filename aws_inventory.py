#!/usr/bin/env python3

import argparse
import boto3
import botocore
import json
import os
import sys
import tempfile

from beaker.cache import CacheManager
from beaker.util import parse_cache_config_options
from botocore.exceptions import ClientError

from itertools import groupby
from collections import Counter, defaultdict
from difflib import SequenceMatcher

try:
    from assume_role import accounts, DEFAULT_REGION  # dict: master profile name: {profile name: child role arn, ...}
except:
    accounts = {}
    DEFAULT_REGION = "ap-southeast-2"

from grouper import group

DEFAULT_EXPIRE = 28800  # 8 hours

try:
    # try to import memcache lib
    import memcache
    # check if memcached is running on localhost
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', 11211))
    if result != 0:
        raise Exception
    cache_opts = {
        'cache.type': 'ext:memcached',
        'cache.url': '127.0.0.1:11211',
    }
except:
    # fallback to file storage
    cache_opts = {
        'cache.type': 'file',
        'cache.data_dir': '/tmp/aws-inventory/data',
        'cache.lock_dir': '/tmp/aws-inventory/lock'
    }


cache = CacheManager(**parse_cache_config_options(cache_opts))


def get_all_profiles():
    # Get profiles from ~/.aws/credentials
    profiles = boto3.session.Session().available_profiles
    for profile in profiles:
        session = boto3.session.Session(
            profile_name=profile,
            region_name=botocore.session.Session(profile=profile).get_config_variable("region") or DEFAULT_REGION,
        )
        yield profile, session
        # discover if we have subaccounts
        if profile in accounts:
            for child in accounts[profile]:
                if child.name in profiles:
                    continue
                try:
                    client = session.client('sts')
                    assumed_creds = client.assume_role(
                        RoleArn=child.arn,
                        RoleSessionName=child.name,
                        DurationSeconds=900,
                    )
                    child_session = boto3.session.Session(
                        aws_access_key_id=assumed_creds["Credentials"]["AccessKeyId"],
                        aws_secret_access_key=assumed_creds["Credentials"]["SecretAccessKey"],
                        aws_session_token=assumed_creds["Credentials"]["SessionToken"],
                        region_name=child.region,
                    )
                    yield child.name, child_session
                except ClientError as e:
                    sys.stderr.write("Can't assume role %s (%s) from %s: %s\n" % (child.arn, child.name, profile, e))


# sorts bastions list by size of the most common substring with host
def bastion_matcher(bastions, host):
    key = sorted(bastions.keys(), key=lambda bastion: SequenceMatcher(None, bastion, host).find_longest_match(0, len(bastion), 0, len(host)).size, reverse=True)[0]
    return bastions[key]


def get_name_from_tags(tags, lower=True):
    if tags:
        name_tag = list(filter(lambda s: s["Key"] == "Name", tags))
        name = name_tag[0]["Value"] if name_tag else ""
        return name.lower() if lower else name
    else:
        return ""


@cache.cache("aws", expire=DEFAULT_EXPIRE)
def get_objects(ssh=False):
    inventory = defaultdict(lambda: {
            "hosts": [],
            "vars": {},
            "children": [],
        })
    inventory["_meta"] = {"hostvars": defaultdict(dict)}
    if ssh:
        inventory["_ssh_config"] = defaultdict(list)

    for profile, session in get_all_profiles():
        group_inventory = defaultdict(lambda: {
            "hosts": [],
            "vars": {},
            "children": [],
        })
        # will be needed to count hosts with the same EC2 Name
        name_counter = Counter()

        # We need only ec2 resources at this stage
        ec2 = session.resource('ec2')
        instances = ec2.instances.filter(
            Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])

        # group by VPC
        for vpc, instances in groupby(sorted(instances, key=lambda s: s.vpc.id), lambda s: s.vpc):
            instances = list(instances)
            bastions = dict(filter(lambda i: "bastion" in i[0], map(lambda i: (get_name_from_tags(i.tags), i.public_ip_address), instances)))

            vpc_name = get_name_from_tags(vpc.tags)

            for instance in sorted(instances, key=lambda s: s.launch_time):
                name = get_name_from_tags(instance.tags)

                name_counter.update([name, ])  # update counter with instance name
                # real name will be group+instance_name+suffix (instance count with the same name)
                # if instance_name already contains group, don't preprend group
                real_name = "-".join(filter(bool, [
                    profile if not name.startswith(profile) else False,
                    name,
                    str(name_counter[name]),
                    ]))

                ip_address = instance.public_ip_address or instance.private_ip_address

                if "bastion" not in real_name and bastions:
                    ip_address = instance.private_ip_address  # always use private ip address for bastion

                    inventory["_meta"]["hostvars"][real_name]["ansible_ssh_common_args"] = "-o ProxyCommand='ssh -W %%h:%%p %s'" % (bastion_matcher(bastions, real_name))
                    if ssh:
                        inventory["_ssh_config"][real_name].append("ProxyJump %s" % (bastion_matcher(bastions, real_name)))

                inventory["_meta"]["hostvars"][real_name]["ansible_ssh_host"] = ip_address
                if ssh:
                    inventory["_ssh_config"][real_name].append("Hostname %s" % ip_address)

                if not vpc_name:
                    inventory[profile]["hosts"].append(real_name)
                else:
                    local_group = "-".join([profile, vpc_name])
                    inventory[local_group]["hosts"].append(real_name)
                    inventory[profile]["children"].append(local_group)

        # remove duplicates from children list
        inventory[profile]["children"] = list(set(inventory[profile]["children"]))
    # a bit hacky, but cacher can't pickle lambdas
    return json.loads(json.dumps(inventory))


def inventory(pretty=True):
    i = get_objects(ssh=False)
    print(json.dumps(group(i), indent=4 if pretty else None))


def test_profiles():
    # Get profiles from ~/.aws/credentials
    profiles = boto3.session.Session().available_profiles
    for profile, session in get_all_profiles():
        try:
            # We need only ec2 resources at this stage
            ec2 = session.resource('ec2')
            instances = ec2.instances.filter(
                Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])

            print("OK in '%s' profile: %d running instances found" % (profile, len(list(instances))))
        except ClientError as e:
            print("FAIL in '%s' profile: %s" % (profile, e))


def ssh_config(output):
    objects = get_objects(ssh=True)["_ssh_config"]

    def config():
        for host in sorted(objects.keys()):
            yield ("Host %s" % host)
            yield ("\n".join(map(lambda s: "    {0}".format(s), objects[host])))
            yield ""
    if output:
        tmpfile = tempfile.mkstemp()[1]
        try:
            with open(tmpfile, "w") as f:
                f.write("\n".join(config()))
            os.rename(tmpfile, output)
        except:
            os.remove(tmpfile)
    else:
        print("\n".join(config()))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="AWS Inventory script. Can be used as an Ansible inventory, or it can generate ssh config")
    parser.add_argument("--clear", action="store_true", help="Clear cache")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("-l", "--list", action="store_true", help="Used by Ansible. Generates inventory in json format and outputs to stdout.")
    actions.add_argument("-t", "--test", action="store_true", help="Test AWS profiles. Connects to all profiles and tries to get instances.")
    actions.add_argument("-c", "--ssh_config")
    args = parser.parse_args()
    if args.clear:
        for ssh in [True, False]:
            cache.invalidate(get_objects, "aws", ssh, expire=DEFAULT_EXPIRE)

    if args.test:
        test_profiles()
    elif args.list:
        inventory()
    else:
        ssh_config(args.ssh_config)
