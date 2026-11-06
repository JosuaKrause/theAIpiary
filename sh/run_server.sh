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
