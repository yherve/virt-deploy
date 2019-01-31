#!/bin/bash

set -eu

CONTAINER_NAME=$1
shift

docker kill $CONTAINER_NAME
