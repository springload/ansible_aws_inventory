### Ansible AWS dynamic inventory script.

## Note
This has been deprecated and no longer maintained, in future refer to https://github.com/springload/aws-ssh

## Requirements

    1. Install python3
    2. pip3 install -r requirements.txt
    3. (Optional) brew install memcached && brew services start memcached
    4. (Optional) update ssh to version >=7.3 to use ssh config.

## How it works

    1. Gathers all profiles from both `~/.aws/credentials` and `~/.aws/config`. Make sure your user credentials are not root credentials, because they don't work with crossaccount access.
    2. For each profile extracts all running instances, groups them by profile name, instance name separated by `-` and VPC name.
    3. It recognises bastion servers! And automatically puts appropriate meta variables, so you don't need to
       hack your ~/.ssh/config in order to connect to bastion-ed instances.
    3. a. If you want to use one bastion server for all VPC in one account, tag the instance with `Global` == `true`
    4. It can work with federated accounts using AssumeRole! Just look into `assume_role.py` for some predefined values or just use `~/.aws/config` with child accounts.

For every profile there are the following groups: "profilename", "profilename+vpcname" and group based on name, separated by dashes, i.e. for name `child1-nonprod-web-01` there are groups `child1`, `child1-nonprod`, `child1-nonprod-web` and `child1-nonprod-web-01`.


## How to use

First of all, edit `assume_role.py` and add your crossaccounts, if needed. Then test the profiles:
  ```sh
    ./aws_inventory.py -t
  ```

It will show if you have insufficient right to list instances in a profile.

After that just add it to ~/.ansible.cfg:
  ```Ini
    [defaults]
    inventory = ~/projects/ansible_aws_inventory/aws_inventory.py
  ```

Or generate a ssh config:
  ```sh
    ~/projects/ansible_aws_inventory/aws_inventory.py -c ~/.ssh/aws_config
  ```

and add the following to the top of your `~/.ssh/config`
  ```Ini
    Include aws_config
  ```

Add this to your .bashrc:
  ```Ini
    alias reconf="cd /<full-path-to>/ansible_aws_inventory/ && ./reconf.sh"
    alias hosts="grep ^Host ~/.ssh/aws_config"
  ```

The first command regenerates ssh config. The second one lists all available hosts.

To refresh ssh config automatically you shall create a cron entry in `/etc/cron.d/aws_reconf`
```bash
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
MAILTO=""

# m h dom mon dow user	command
51 9 * * * root su <your_user> -c "cd /<full-path-to>/ansible_aws_inventory/ && ./reconf.sh"
``` 

Enjoy!


## Examples

Now you can just ssh to nodes from the list.

To see all available groups:

    $ansible localhost -m debug -a 'var=groups'
    localhost | SUCCESS => {
        "changed": false,
        "groups": {
            "child1": [
                "child1-preview-com-01-1",
                "child1-wianode01-1",
                "child1-wianode01-2",
                "child1-preview-ec2-01-1",
                "child1-wianode01-3",
                "child1-apexnode-1"
            ],
            "childN": [
                "childN-nonprod-bastion-01-1",
                "childN-nonprod-ec2-01-1",
            ],
            "all": [
                "childN-nonprod-bastion-01-1",
                "childN-nonprod-ec2-01-1",
                "child1-preview-com-01-1",
                "child1-wianode01-1",
                "child1-wianode01-2",
                "child1-preview-ec2-01-1",
                "child1-wianode01-3",
                "child1-apexnode-1"
            ],
            "dev": [],
            "ungrouped": [
                "localhost"
            ]
        }
    }

## Ansible examples:

    $ansible -m ping childN
    childN-nonprod-bastion-01-1 | SUCCESS => {
        "changed": false,
        "ping": "pong"
    }
    childN-nonprod-ec2-01-1 | SUCCESS => {
        "changed": false,
        "ping": "pong"
    }

## Important

All your team should name aws profiles in `~/.aws/credentials` and `~/.aws/config` identically across all their machines.
