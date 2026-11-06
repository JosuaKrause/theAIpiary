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

BASE="${BASE:-userdata/provider}"
mkdir -p "${BASE}/"
pushd "${BASE}"
BASE="$(pwd)"
popd

ENV_FILE="${ENV_FILE:-${BASE}/swai/provider.env}"

PYTHON="${PYTHON:-python}"
DATE=$(date "+%Y-%m-%d")

if [ ! -f "${ENV_FILE}" ]; then
    mkdir -p "$(dirname -- ${ENV_FILE})"
    cp "provider.env.sample" "${ENV_FILE}"
    echo "created env file at ${ENV_FILE} please fill in all values and run again"
    exit 1
else
    source "${ENV_FILE}"
fi

if [ -z "${AIPIARY_WORKER_TOKEN}" ] || [ -z "${AIPIARY_USER}" ] || [ -z "${AIPIARY_API_URL}" ]; then
    echo "missing values in env file"
    exit 2
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

start_smind() {
    DEVICE=$1
    mkdir -p "${BASE}/smind/"
    pushd "src/"
    AIPIARY_API_URL="${AIPIARY_API_URL}" \
    AIPIARY_USER="${AIPIARY_USER}" \
    AIPIARY_WORKER_TOKEN="${AIPIARY_WORKER_TOKEN}" \
        ${PYTHON} -u -m scattermind \
        --env "${ENV_FILE}" \
        --version-file "${BASE}/version.txt" \
        --config "${ROOT}/local/smind-config.json" \
        --device "${DEVICE}" \
        worker \
        --graph "${ROOT}/local/graphs/" \
        >> "${BASE}/smind/smind-${DATE}.log" 2>&1 &
    popd
}

start_provider() {
    mkdir -p "${BASE}/swai/"
    cd "src/"
    AIPIARY_API_URL="${AIPIARY_API_URL}" \
    AIPIARY_USER="${AIPIARY_USER}" \
    AIPIARY_WORKER_TOKEN="${AIPIARY_WORKER_TOKEN}" \
    CONFIG_PATH="${ROOT}/local/provider.config.json" \
    VERSION_PATH="${BASE}/version.txt" \
        exec \
        ${PYTHON} -u -m swai_provider \
        --env "${ENV_FILE}" \
        >> "${BASE}/swai/swai_provider-${DATE}.log" 2>&1
}

VERSION_PATH="${BASE}/version.txt" make -s version-file

start_redis rmain 6381
start_redis rbody 6382
start_redis rdata 6383
start_redis rcache 6384

DEVICE="${DEVICE:-auto}"

start_smind "${DEVICE}"
start_provider
