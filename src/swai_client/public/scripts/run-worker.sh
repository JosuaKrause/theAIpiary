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

HAS_CUDA=1
if ! command -v nvidia-smi &> /dev/null; then
    HAS_CUDA=
fi

HAS_DOCKER=1
if ! command -v docker &> /dev/null; then
    HAS_DOCKER=
fi

if [ -z "${HAS_CUDA}" ] || [ -z "${HAS_DOCKER}" ]; then
    if [ -z "${HAS_CUDA}" ]; then
        echo "could not find cuda. please make sure it is installed on the system!"
    fi
    if [ -z "${HAS_DOCKER}" ]; then
        echo "could not find docker. please make sure it is installed on the system!"
    fi
    exit 1
fi

# The server that serves this script fills in the values below from its
# server.env (OWN_URL, PROVIDER_REGISTRY, MODEL_URL). Each can be overridden
# through the environment, e.g., AIPIARY_URL=https://example.com/ ./run-worker.sh
AIPIARY_URL="${AIPIARY_URL:-@@PUBLIC_URL@@}"
PROVIDER_REGISTRY="${PROVIDER_REGISTRY:-@@PROVIDER_REGISTRY@@}"
MODEL_URL="${MODEL_URL:-@@MODEL_URL@@}"

# true if the value is empty or was not filled in by the server
not_set() {
    [ -z "$1" ] || [[ "$1" == @@*@@ ]]
}

if not_set "${AIPIARY_URL}"; then
    echo "the server URL is not configured."
    echo "run the script as AIPIARY_URL=<server URL> ./run-worker.sh"
    exit 1
fi
AIPIARY_URL="${AIPIARY_URL%/}/"

BASE=aipiary
mkdir -p "${BASE}"
cd "${BASE}"

DOCKER_COMPOSE="docker-compose.yml"
if [ ! -f "${DOCKER_COMPOSE}" ]; then
    echo "downloading ${DOCKER_COMPOSE}"
    curl -fL "${AIPIARY_URL}scripts/docker-compose.yml" -o "${DOCKER_COMPOSE}"
fi

# docker compose reads the image registry from this file
COMPOSE_ENV=".env"
if [ ! -f "${COMPOSE_ENV}" ]; then
    if not_set "${PROVIDER_REGISTRY}"; then
        echo "the image registry is not configured."
        echo "run the script as PROVIDER_REGISTRY=<registry> ./run-worker.sh"
        exit 1
    fi
    echo "PROVIDER_REGISTRY='${PROVIDER_REGISTRY%/}'" > "${COMPOSE_ENV}"
fi

MODEL_DIR="userdata/models"
mkdir -p "${MODEL_DIR}"
if not_set "${MODEL_URL}"; then
    if ! compgen -G "${MODEL_DIR}/*.gguf" > /dev/null; then
        echo "this server does not provide a model download."
        echo "place the GGUF model file that the worker image expects in"
        echo "$(pwd)/${MODEL_DIR}/ and run again."
        exit 1
    fi
else
    MODEL_NAME="${MODEL_URL%%\?*}"
    MODEL_FILE="${MODEL_DIR}/${MODEL_NAME##*/}"
    if [ ! -f "${MODEL_FILE}" ]; then
        echo "downloading ${MODEL_FILE}"
        if ! curl -fL "${MODEL_URL}" -o "${MODEL_FILE}"; then
            rm -f -- "${MODEL_FILE}"
            echo "could not download model automatically."
            echo "download the model from"
            echo "${MODEL_URL}"
            echo "and place it here:"
            echo "$(pwd)/${MODEL_FILE}"
            exit 1
        fi
    fi
fi

AIPIARY_ENV="userdata/swai/provider.env"
if [ ! -f "${AIPIARY_ENV}" ]; then
    mkdir -p "$(dirname "${AIPIARY_ENV}")"
    read -r -p "AIpiary user name (email): " AIPIARY_USER
    read -r -p "AIpiary worker token: " AIPIARY_WORKER_TOKEN
    echo "AIPIARY_API_URL='${AIPIARY_URL}'" > "${AIPIARY_ENV}"
    echo "AIPIARY_USER='${AIPIARY_USER}'" >> "${AIPIARY_ENV}"
    echo "AIPIARY_WORKER_TOKEN='${AIPIARY_WORKER_TOKEN}'" >> "${AIPIARY_ENV}"
fi

docker compose -f "${DOCKER_COMPOSE}" up || echo "done $?"
