#!/usr/bin/env python
# -*- coding: utf-8 -*-

from collections import namedtuple

DEFAULT_REGION = "ap-southeast-2"

account_template = namedtuple("account_template", ["name", "number", "region"])
account = namedtuple("account", ["name", "arn", "region"])
accounts = {
        "main": {account(a.name, "arn:aws:iam::%s:role/crossinventory" % a.number, a.region) for a in [
            account_template("child1", "012345678912", DEFAULT_REGION),
            # ...
            account_template("childN", "010987654321", DEFAULT_REGION),
        ]}
}

if __name__ == "__main__":
    print(accounts)
