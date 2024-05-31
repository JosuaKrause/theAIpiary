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
set -x

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

ROOT="$(pwd)"

BASE="${BASE:-userdata/server}"
mkdir -p "${BASE}/"
pushd "${BASE}"
BASE="$(pwd)"
popd

ENV_FILE="${ENV_FILE:-${BASE}/swai/server.env}"

PYTHON="${PYTHON:-python}"
DATE=$(date "+%Y-%m-%d")

if [ ! -f "${ENV_FILE}" ]; then
    mkdir -p "$(dirname -- ${ENV_FILE})"
    cp "server.env.sample" "${ENV_FILE}"
    echo "created env file at ${ENV_FILE} please fill in all values and run again"
    exit 1
fi

start_redis() {
    REDIS_NAME=$1
    REDIS_PORT=$2
    REDIS_PATH="${BASE}/${REDIS_NAME}/"
    mkdir -p "${REDIS_PATH}"
    pushd "${REDIS_PATH}"
    redis-server \
        "${ROOT}/local/redis/${REDIS_NAME}.conf" \
        --port "${REDIS_PORT}" \
        >> "${REDIS_PATH}/redis-${DATE}.log" 2>&1 &
    popd
}

start_server() {
    mkdir -p "${BASE}/swai/"
    pushd "src/"
    HISTORY_PATH="${BASE}/.cmd_history" \
    CONFIG_PATH="${ROOT}/local/server.config.json" \
    VERSION_PATH="${BASE}/version.txt" \
        ${PYTHON} -u -m swai_server \
        --dedicated \
        --env "${ENV_FILE}" \
        >> "${BASE}/swai/swai_server-${DATE}.log" 2>&1 &
    popd
}

VERSION_PATH="${BASE}/version.txt" make -s version-file

start_redis rserver 6385

DEVICE="${DEVICE:-auto}"

start_server

make run-ts
