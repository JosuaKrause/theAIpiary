#!/usr/bin/env bash
#
# Copyright (c) 2024 Josua Krause - All Rights Reserved
#
# THE CONTENTS OF THIS PROJECT ARE PROPRIETARY AND CONFIDENTIAL.
# UNAUTHORIZED COPYING, TRANSFERRING OR REPRODUCTION OF THE CONTENTS OF
# THIS PROJECT, VIA ANY MEDIUM IS STRICTLY PROHIBITED.
#
# The receipt or possession of the source code and/or any parts thereof does
# not convey or imply any right to use them for any purpose other than the
# purpose for which they were provided to you.
#
# The software is provided "AS IS", without warranty of any kind, express or
# implied, including but not limited to the warranties of merchantability,
# fitness for a particular purpose and non infringement. In no event shall the
# authors or copyright holders be liable for any claim, damages or other
# liability, whether in an action of contract, tort or otherwise, arising from,
# out of or in connection with the software or the use or other dealings in the
# software.
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the software.
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
    URL="${DOCKER_LOGIN_SERVER}${IMAGE}"
    if ! docker pull "${URL}" &> /dev/null ; then
        echo "pushing ${IMAGE} to ${URL}"

        docker tag "${IMAGE}" "${URL}"
        docker push "${URL}"
        docker rmi "${URL}"
        sleep 1
    else
        echo "${URL} already exists"
    fi
}

dpush "worker" "${IMAGE_TAG}"
dpush "api" "${IMAGE_TAG}"
dpush "rmain" "${REDIS_DOCKER_VERSION}"
dpush "rdata" "${REDIS_DOCKER_VERSION}"
dpush "rcache" "${REDIS_DOCKER_VERSION}"
dpush "rbody" "${REDIS_DOCKER_VERSION}"
