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

BUILDTMP="buildtmp_server"

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
IMAGE_BASE="swai-server"
PORT="${PORT:-8080}"

if [ ! -z "${DEV}" ]; then
    IMAGE_BASE="${IMAGE_BASE}-dev"
fi

make -s version-file
trap 'rm -- version.txt' EXIT

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
    DOCKER_COMPOSE_OUT="docker-compose.server.dev.yml"
    WEBAPP_STORAGE_HOME="./userdata/server"
    DOCKER_LOGIN_SERVER=
else
    DOCKER_COMPOSE_OUT="docker-compose.server.yml"
    WEBAPP_STORAGE_HOME=
    DOCKER_LOGIN_SERVER=
fi

make install-ts
make ts-build
cp -R "src/swai_client/build/" "${BUILDTMP}/build"

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

DEFAULT_ENV_FILE=deploy/default.server.env
echo "# created by sh/build_server.sh" > "${DEFAULT_ENV_FILE}"
echo "DOCKER_API=${IMAGE_BASE}-api:${IMAGE_TAG}" >> "${DEFAULT_ENV_FILE}"
echo "DOCKER_RSERVER=${IMAGE_BASE}-rserver:${REDIS_DOCKER_VERSION}" >> "${DEFAULT_ENV_FILE}"
if [ ! -z "${WEBAPP_STORAGE_HOME}" ]; then
    echo "{WEBAPP_STORAGE_HOME}=${WEBAPP_STORAGE_HOME}" >> "${DEFAULT_ENV_FILE}"
fi

! read -r -d '' PY_COMPOSE <<'EOF'
import os
import sys

prefix = sys.argv[1]
dcompose = sys.argv[2]
denv = sys.argv[3]
dout = sys.argv[4]
substitute = {}
with open(denv, "r", encoding="utf-8") as fin:
    for line in fin:
        line = line.rstrip().split("#", 1)[0].strip()
        if not line:
            continue
        variable, value = line.split("=", 1)
        variable = f"${variable}".strip()
        value = f"{value.strip()}"
        if variable.startswith("$DOCKER_"):
            value = f"{prefix}{value}"
        if value.startswith("@"):
            with open(value[1:], "r", encoding="utf-8") as tin:
                value = tin.read()
        substitute[variable] = value
with open(dcompose, "r", encoding="utf-8") as din:
    content = din.read()
for variable, value in sorted(
        substitute.items(), key=lambda e: len(e[0]), reverse=True):
    content = content.replace(variable, value)
with open(dout, "w", encoding="utf-8") as fout:
    fout.write(content)
EOF

${PYTHON} -c "${PY_COMPOSE}" "${DOCKER_LOGIN_SERVER}" "deploy/docker-compose.server.yml" "${DEFAULT_ENV_FILE}" "${DOCKER_COMPOSE_OUT}"

echo "docker compose is ready at ${DOCKER_COMPOSE_OUT}"
echo "make sure to call make dockerpush before updating"
if [ ! -z "${DEV}" ]; then
    echo "run 'make compose-server' next to start the app on http://localhost:8080/login/"
elif [ -z "${CI}" ]; then
    echo "================================================="
    grep -Ev '^\s*$|^\s*\#' "${DOCKER_COMPOSE_OUT}"
    echo "# eof"
else
    echo "run 'make build-server' locally (without dockerpush) to get the docker compose file"
fi
