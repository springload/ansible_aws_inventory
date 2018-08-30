#!/usr/bin/env bash

if [ ! -f "${HOME}/.ssh/aws_config" ] ; then
    touch "${HOME}/.ssh/aws_config"
fi;

docker run --rm -v "${HOME}/.aws/config":/home/appuser/.aws/config:ro \
    -v "${HOME}/.aws/credentials":/home/appuser/.aws/credentials:ro \
    -v "${HOME}/.ssh/aws_config":/app/aws_config \
    $(docker build -q . --tag "ansible_aws_inventory" --build-arg USER_ID=$(id -u) --build-arg USER_GROUP_ID=$(id -g)) \
    ./aws_inventory.py -c /app/aws_config --clear