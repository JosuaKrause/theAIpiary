#!/usr/bin/env bash
#
# Copyright (C) 2024 Josua Krause
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
set -e

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

# runs the images of make build-server-dev with deploy/docker-compose.server.yml
# and userdata/server as the data directory
IMAGE_ENV_FILE=deploy/default.server.dev.env
if [ ! -f "${IMAGE_ENV_FILE}" ]; then
    echo "${IMAGE_ENV_FILE} not found. run 'make build-server-dev' first"
    exit 1
fi

AIPIARY_DATA="$(pwd)/userdata/server"
ENV_FILE="${AIPIARY_DATA}/swai/server.env"
if [ ! -f "${ENV_FILE}" ]; then
    mkdir -p "$(dirname -- ${ENV_FILE})"
    cp "server.env.sample" "${ENV_FILE}"
    echo "created env file at ${ENV_FILE} please fill in all values and run again"
    exit 1
fi

AIPIARY_DATA="${AIPIARY_DATA}" docker compose \
    -f deploy/docker-compose.server.yml \
    --env-file "${IMAGE_ENV_FILE}" \
    up || echo "done $?"
