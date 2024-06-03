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

BUILDTMP="buildtmp_provider"

rm -rf "${BUILDTMP}"
mkdir -p "${BUILDTMP}"

PYTHON="${PYTHON:-python}"

REDIS_VERSION_FILE="${BUILDTMP}/redis.version"
DEVMODE_CONF_FILE="${BUILDTMP}/devmode.conf"
REQUIREMENTS_PROVIDER_FILE="${BUILDTMP}/requirements.provider.txt"
REQUIREMENTS_WORKER_FILE="${BUILDTMP}/requirements.worker.txt"
SMIND_CFG="${BUILDTMP}/smind-config.json"
SMIND_GRS="${BUILDTMP}/graphs/"
RMAIN_CFG="${BUILDTMP}/rmain.conf"
RDATA_CFG="${BUILDTMP}/rdata.conf"
RCACHE_CFG="${BUILDTMP}/rcache.conf"
RBODY_CFG="${BUILDTMP}/rbody.conf"
REDIS_RUN_SCRIPT="${BUILDTMP}/run_redis.sh"

cp "deploy/redis/rmain.conf" "${RMAIN_CFG}"
cp "deploy/redis/rdata.conf" "${RDATA_CFG}"
cp "deploy/redis/rcache.conf" "${RCACHE_CFG}"
cp "deploy/redis/rbody.conf" "${RBODY_CFG}"
cp "deploy/redis.version" "${REDIS_VERSION_FILE}"
cp "deploy/devmode.conf" "${DEVMODE_CONF_FILE}"
cp "deploy/run_redis.sh" "${REDIS_RUN_SCRIPT}"
cp "deploy/smind-config.json" "${SMIND_CFG}"
cp -R "deploy/graphs/" "${SMIND_GRS}"

IMAGE_TAG="${IMAGE_TAG:-$(make -s name)}"
IMAGE_BASE="aipiary"

if [ ! -z "${DEV}" ]; then
    IMAGE_BASE="${IMAGE_BASE}-dev"
fi

VERSION_PATH="version.provider.txt"
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

cp "requirements.provider.txt" "${REQUIREMENTS_PROVIDER_FILE}"
cp "requirements.worker.txt" "${REQUIREMENTS_WORKER_FILE}"
if [ ! -z "${DEVMODE}" ]; then
    echo "library dev mode active"

    replace_lib "${REQUIREMENTS_PROVIDER_FILE}" "quick-server" "${QUICK_SERVER_PATH}" "${QUICK_SERVER_URL}" "${QUICK_SERVER_BRANCH}"
    replace_lib "${REQUIREMENTS_PROVIDER_FILE}" "redipy" "${REDIPY_PATH}" "${REDIPY_URL}" "${REDIPY_BRANCH}"
    replace_lib "${REQUIREMENTS_PROVIDER_FILE}" "scattermind" "${SMIND_PATH}" "${SMIND_URL}" "${SMIND_BRANCH}"

    replace_lib "${REQUIREMENTS_WORKER_FILE}" "quick-server" "${QUICK_SERVER_PATH}" "${QUICK_SERVER_URL}" "${QUICK_SERVER_BRANCH}"
    replace_lib "${REQUIREMENTS_WORKER_FILE}" "redipy" "${REDIPY_PATH}" "${REDIPY_URL}" "${REDIPY_BRANCH}"
    replace_lib "${REQUIREMENTS_WORKER_FILE}" "scattermind" "${SMIND_PATH}" "${SMIND_URL}" "${SMIND_BRANCH}"
fi

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
    --build-arg "REQUIREMENTS_PATH=${REQUIREMENTS_PROVIDER_FILE}" \
    --build-arg "SMIND_CONFIG=${SMIND_CFG}" \
    --build-arg "SMIND_GRAPHS=${SMIND_GRS}" \
    -f deploy/provider.Dockerfile \
    .

docker_build \
    "${IMAGE_BASE}-worker:${IMAGE_TAG}" \
    --build-arg "REQUIREMENTS_PATH=${REQUIREMENTS_WORKER_FILE}" \
    --build-arg "SMIND_CONFIG=${SMIND_CFG}" \
    --build-arg "SMIND_GRAPHS=${SMIND_GRS}" \
    -f deploy/worker.Dockerfile \
    .

echo "rmain:${REDIS_DOCKER_VERSION}" > "${BUILDTMP}/rmain.version"

docker_build \
    "${IMAGE_BASE}-rmain:${REDIS_DOCKER_VERSION}" \
    --build-arg "PORT=6379" \
    --build-arg "CFG_FILE=${RMAIN_CFG}" \
    --build-arg "REDIS_VERSION_FILE=${BUILDTMP}/rmain.version" \
    --build-arg "REDIS_RUN_SCRIPT=${REDIS_RUN_SCRIPT}" \
    -f deploy/redis.Dockerfile \
    .

echo "rdata:${REDIS_DOCKER_VERSION}" > "${BUILDTMP}/rdata.version"

docker_build \
    "${IMAGE_BASE}-rdata:${REDIS_DOCKER_VERSION}" \
    --build-arg "PORT=6379" \
    --build-arg "CFG_FILE=${RDATA_CFG}" \
    --build-arg "REDIS_VERSION_FILE=${BUILDTMP}/rdata.version" \
    --build-arg "REDIS_RUN_SCRIPT=${REDIS_RUN_SCRIPT}" \
    -f deploy/redis.Dockerfile \
    .

echo "rcache:${REDIS_DOCKER_VERSION}" > "${BUILDTMP}/rcache.version"

docker_build \
    "${IMAGE_BASE}-rcache:${REDIS_DOCKER_VERSION}" \
    --build-arg "PORT=6379" \
    --build-arg "CFG_FILE=${RCACHE_CFG}" \
    --build-arg "REDIS_VERSION_FILE=${BUILDTMP}/rcache.version" \
    --build-arg "REDIS_RUN_SCRIPT=${REDIS_RUN_SCRIPT}" \
    -f deploy/redis.Dockerfile \
    .

echo "rbody:${REDIS_DOCKER_VERSION}" > "${BUILDTMP}/rbody.version"

docker_build \
    "${IMAGE_BASE}-rbody:${REDIS_DOCKER_VERSION}" \
    --build-arg "PORT=6379" \
    --build-arg "CFG_FILE=${RBODY_CFG}" \
    --build-arg "REDIS_VERSION_FILE=${BUILDTMP}/rbody.version" \
    --build-arg "REDIS_RUN_SCRIPT=${REDIS_RUN_SCRIPT}" \
    -f deploy/redis.Dockerfile \
    .
