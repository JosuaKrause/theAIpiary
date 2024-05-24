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
set -ex

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

BASE="userdata/provider"
ROOT="../.."

mkdir -p "${BASE}/"

PYTHON="${PYTHON:-python}"
DATE=$(date "+%Y-%m-%d")

start_redis() {
    REDIS_NAME=$1
    REDIS_PORT=$2
    REDIS_PATH="${BASE}/${REDIS_NAME}/"
    mkdir -p "${REDIS_PATH}"
    pushd "${REDIS_PATH}"
    redis-server \
        "../${ROOT}/deploy/redis_mac/${REDIS_NAME}.conf" \
        --port "${REDIS_PORT}" \
        >> "redis-${DATE}.log" 2>&1 &
    popd
}

start_smind() {
    DEVICE=$1
    mkdir -p "${BASE}/smind/"
    pushd "src/"
    ${PYTHON} -u -m scattermind \
        --version-file "../${BASE}/version.txt" \
        --config "../deploy/smind-config-mac.json" \
        --device "${DEVICE}" \
        worker \
        --graph "../deploy/graphs_mac/" \
        >> "../${BASE}/smind/smind-${DATE}.log" 2>&1 &
    popd
}

start_provider() {
    mkdir -p "${BASE}/swai/"
    pushd "src/"
    SWAI_API_URL="http://localhost:3000/api" \
    SWAI_USER="admin" \
    SWAI_WORKER_TOKEN="${SWAI_WORKER_TOKEN}" \
    HISTORY_PATH="../${BASE}/.cmd_history" \
    CONFIG_PATH="../mac.config.json" \
    VERSION_PATH="../${BASE}/version.txt" \
    PUBLIC_PATH="../public/" \
        ${PYTHON} -u -m swai_provider \
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
