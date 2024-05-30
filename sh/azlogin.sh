#!/usr/bin/env bash

set -e

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

DOCKER_REGISTRY="aipiary"

az login
az acr login --name "${DOCKER_REGISTRY}"
