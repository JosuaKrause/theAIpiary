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

ENV_FILE="system.env"

if [ ! -f "${ENV_FILE}" ]; then
    cp "system.env.sample" "${ENV_FILE}"
    echo "created env file at ${ENV_FILE} please fill in all values and run again"
    exit 1
else
    source "${ENV_FILE}"
fi

echo "${DOCKER_TOKEN}" | docker login --username "${DOCKER_USER}" --password-stdin

IMAGE_TAG="${IMAGE_TAG:-$(make -s name)}"
IMAGE_BASE="aipiary"
DOCKER_LOGIN_SERVER="aipiary/"

DEVMODE_CONF_FILE="deploy/devmode.conf"
REDIS_VERSION_FILE="deploy/redis.version"

source "${DEVMODE_CONF_FILE}"
source "${REDIS_VERSION_FILE}"

if [ ! -z "${DEVMODE}" ]; then
    REDIS_DOCKER_VERSION="${REDIS_DOCKER_VERSION}-devmode"
fi

dpush() {
    IMAGE="${IMAGE_BASE}-$1:$2"
    IMAGE_LATEST="${IMAGE_BASE}-$1"
    URL="${DOCKER_LOGIN_SERVER}${IMAGE}"
    URL_LATEST="${DOCKER_LOGIN_SERVER}${IMAGE_LATEST}"
    if ! docker pull "${URL}" &> /dev/null ; then
        echo "pushing ${IMAGE} to ${URL}"

        docker tag "${IMAGE}" "${URL}"
        docker push "${URL}"
        docker rmi "${URL}"
        sleep 1
    else
        echo "${URL} already exists"
    fi
    echo "pushing ${IMAGE} to ${URL_LATEST}"

    docker tag "${IMAGE}" "${URL_LATEST}"
    docker push "${URL_LATEST}"
    docker rmi "${URL_LATEST}"
    sleep 1
}

dpush "worker" "${IMAGE_TAG}"
dpush "api" "${IMAGE_TAG}"
dpush "rmain" "${REDIS_DOCKER_VERSION}"
dpush "rdata" "${REDIS_DOCKER_VERSION}"
dpush "rcache" "${REDIS_DOCKER_VERSION}"
dpush "rbody" "${REDIS_DOCKER_VERSION}"
