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

source sh/docker_registry.sh

load_system_env

BUILDTMP="buildtmp_server"

rm -rf "${BUILDTMP}"
mkdir -p "${BUILDTMP}"

PYTHON="${PYTHON:-python}"

REDIS_VERSION_FILE="${BUILDTMP}/redis.version"
DEVMODE_CONF_FILE="${BUILDTMP}/devmode.conf"
REQUIREMENTS_SERVER_FILE="${BUILDTMP}/requirements.server.txt"
RSERVER_CFG="${BUILDTMP}/rserver.conf"
REDIS_RUN_SCRIPT="${BUILDTMP}/run_redis.sh"
CONFIG_PATH="${BUILDTMP}/config.json"

cp "deploy/redis/rserver.conf" "${RSERVER_CFG}"
cp "deploy/redis.version" "${REDIS_VERSION_FILE}"
cp "deploy/devmode.conf" "${DEVMODE_CONF_FILE}"
cp "deploy/run_redis.sh" "${REDIS_RUN_SCRIPT}"
cp "deploy/server.config.json" "${CONFIG_PATH}"

IMAGE_TAG="${IMAGE_TAG:-$(make -s name)}"
IMAGE_BASE="aipiary-server"
PORT="${PORT:-8080}"

if [ ! -z "${DEV}" ]; then
    IMAGE_BASE="${IMAGE_BASE}-dev"
fi

VERSION_PATH=version.server.txt
VERSION_PATH="${VERSION_PATH}" make -s version-file
trap "rm -- ${VERSION_PATH}" EXIT

echo "building ${IMAGE_BASE}"

source "${DEVMODE_CONF_FILE}"
source "${REDIS_VERSION_FILE}"

if [ ! -z "${DEVMODE}" ]; then
    REDIS_DOCKER_VERSION="${REDIS_DOCKER_VERSION}-devmode"
fi

QUICK_SERVER_PATH="../quick_server"
REDIPY_PATH="../redipy"
SMIND_PATH="../scattermind"

QUICK_SERVER_URL="git+https://github.com/JosuaKrause/quick_server.git"
REDIPY_URL="git+https://github.com/JosuaKrause/redipy.git"
SMIND_URL="git+https://github.com/JosuaKrause/scattermind.git"

! read -r -d '' PY_LIB <<'EOF'
import os
import sys

fname = sys.argv[1]
lib_name = sys.argv[2]
lib_replace = sys.argv[3]
lines = []
with open(fname, "r", encoding="utf-8") as fin:
    for line in fin:
        line = line.rstrip()
        if not line.startswith(lib_name):
            lines.append(line)
            continue
        lines.append(lib_replace)
with open(fname, "w", encoding="utf-8") as fout:
    fout.write("\n".join(lines))
EOF

replace_lib() {
    REQ_FILE="$1"
    LIB="$2"
    LIB_PATH="$3"
    LIB_URL="$4"
    LIB_BRANCH="$5"
    if [ -d "${LIB_PATH}" ]; then
        pushd "${LIB_PATH}"
        LIB_HASH=$(git describe --match NOTATAG --always --abbrev=40 --dirty='!')
        popd
    else
        echo "${LIB_PATH} not found! using branch ${LIB_BRANCH} instead"
        LIB_HASH="${LIB_BRANCH}"
    fi
    case "${LIB_HASH}" in *!)
        echo "library ${LIB} at ${LIB_PATH} is dirty!"
        exit 1
    esac
    ${PYTHON} -c "${PY_LIB}" "${REQ_FILE}" "${LIB}" "${LIB_URL}@${LIB_HASH}"
}

cp "requirements.server.txt" "${REQUIREMENTS_SERVER_FILE}"
if [ ! -z "${DEVMODE}" ]; then
    echo "library dev mode active"

    replace_lib "${REQUIREMENTS_SERVER_FILE}" "quick-server" "${QUICK_SERVER_PATH}" "${QUICK_SERVER_URL}" "${QUICK_SERVER_BRANCH}"
    replace_lib "${REQUIREMENTS_SERVER_FILE}" "redipy" "${REDIPY_PATH}" "${REDIPY_URL}" "${REDIPY_BRANCH}"
    replace_lib "${REQUIREMENTS_SERVER_FILE}" "scattermind" "${SMIND_PATH}" "${SMIND_URL}" "${SMIND_BRANCH}"
fi

if [ ! -z "${DEV}" ]; then
    IMAGE_ENV_FILE="deploy/default.server.dev.env"
    IMAGE_REGISTRY=
else
    IMAGE_ENV_FILE="deploy/default.server.env"
    IMAGE_REGISTRY="${SERVER_REGISTRY%/}"
    if [ -z "${IMAGE_REGISTRY}" ]; then
        echo "SERVER_REGISTRY is not set (see system.env.sample)." \
            "the image settings will reference local image names"
    fi
fi

make install-ts
make ts-build
mv "src/swai_client/build/" "${BUILDTMP}/build/"

docker_build() {
    ARGS=("$@")
    if [ ! -z "${VERBOSE}" ]; then
        ARGS+=("--progress=plain")
    fi
    if [ ! -z "${NO_CACHE}" ]; then
        ARGS+=("--no-cache")
    fi
    _docker_build "${ARGS[@]}"
}

_docker_build() {
    TAG="$1"
    shift
    if [ ! -z "${DEV}" ]; then
        docker build -t "${TAG}" "${@}"
    else
        docker buildx build --platform linux/amd64 -t "${TAG}" "${@}"
    fi
    echo "built ${TAG}"
}

docker_build \
    "${IMAGE_BASE}-api:${IMAGE_TAG}" \
    --build-arg "REQUIREMENTS_PATH=${REQUIREMENTS_SERVER_FILE}" \
    --build-arg "CONFIG_PATH=${CONFIG_PATH}" \
    --build-arg "PORT=${PORT}" \
    -f deploy/server.Dockerfile \
    .

echo "rserver:${REDIS_DOCKER_VERSION}" > "${BUILDTMP}/rserver.version"

docker_build \
    "${IMAGE_BASE}-rserver:${REDIS_DOCKER_VERSION}" \
    --build-arg "PORT=6379" \
    --build-arg "CFG_FILE=${RSERVER_CFG}" \
    --build-arg "REDIS_VERSION_FILE=${BUILDTMP}/rserver.version" \
    --build-arg "REDIS_RUN_SCRIPT=${REDIS_RUN_SCRIPT}" \
    -f deploy/redis.Dockerfile \
    .

# the image settings deploy/docker-compose.server.yml needs, in the format of
# its .env file (see deploy/server.compose.env.sample)
{
    echo "# written by sh/build_server.sh"
    echo "SERVER_REGISTRY=${IMAGE_REGISTRY}"
    echo "AIPIARY_VERSION=${IMAGE_TAG}"
    echo "AIPIARY_REDIS_VERSION=${REDIS_DOCKER_VERSION}"
    if [ ! -z "${DEV}" ]; then
        echo "AIPIARY_IMAGE_BASE=${IMAGE_BASE}"
    fi
} > "${IMAGE_ENV_FILE}"

echo "the image settings for deploy/docker-compose.server.yml" \
    "are in ${IMAGE_ENV_FILE}:"
grep -v '^#' "${IMAGE_ENV_FILE}"
if [ ! -z "${DEV}" ]; then
    echo "run 'make compose-server' next to start the app on http://localhost:8080/login/"
else
    echo "run 'make dockerpush-server' to push the images, then copy the" \
        "settings above into the .env file next to the compose file on the host"
fi
