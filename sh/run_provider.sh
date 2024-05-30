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

BASE="userdata/provider"
ENV_FILE="${ENV_FILE:-${BASE}/swai/provider.env}"
ROOT="../.."

mkdir -p "${BASE}/"

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
        "../${ROOT}/local/redis/${REDIS_NAME}.conf" \
        --port "${REDIS_PORT}" \
        >> "redis-${DATE}.log" 2>&1 &
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
        --env "../${ENV_FILE}" \
        --version-file "../${BASE}/version.txt" \
        --config "../local/smind-config.json" \
        --device "${DEVICE}" \
        worker \
        --graph "../local/graphs/" \
        >> "../${BASE}/smind/smind-${DATE}.log" 2>&1 &
    popd
}

start_provider() {
    mkdir -p "${BASE}/swai/"
    pushd "src/"
    AIPIARY_API_URL="${AIPIARY_API_URL}" \
    AIPIARY_USER="${AIPIARY_USER}" \
    AIPIARY_WORKER_TOKEN="${AIPIARY_WORKER_TOKEN}" \
    CONFIG_PATH="../local/provider.config.json" \
    VERSION_PATH="../${BASE}/version.txt" \
        ${PYTHON} -u -m swai_provider \
        --env "../${ENV_FILE}" \
        >> "../${BASE}/swai/swai_provider-${DATE}.log" 2>&1
    popd
}

make -s version-file
mv version.txt "${BASE}/version.txt"

start_redis rmain 6381
start_redis rbody 6382
start_redis rdata 6383
start_redis rcache 6384

DEVICE="${DEVICE:-auto}"

start_smind "${DEVICE}"
start_provider
