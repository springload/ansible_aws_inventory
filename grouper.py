#!/usr/bin/env python
# -*- coding: utf-8 -*-

from itertools import groupby
from collections import defaultdict
import json


def grouper(name):
    splitted = name.split("-")
    ret = []
    for x in range(1, len(splitted)):
        ret.append("-".join(name.split("-", x)[:x]))

    return list(filter(lambda s: s != name, ret))


def group(inventory):
    grouptemplate = defaultdict(lambda: {
        "hosts": [],
        "children": [],
    })
    # get profiles and items
    for profile, var in sorted(inventory.items(), key=lambda item: item[0]):
        if "hosts" in var:
            for groups, hosts in groupby(sorted(var["hosts"]), grouper):
                hosts = list(hosts)
                groups = list(map(lambda s: "-".join(["_group", s]), groups))
                # group groups by pairs
                for parent, children in zip(groups, groups[1:]):
                    if children not in grouptemplate[parent]["children"]:
                        grouptemplate[parent]["children"].append(children)
                grouptemplate[groups[-1]]["hosts"] = hosts

    inventory.update(grouptemplate)
    return inventory
