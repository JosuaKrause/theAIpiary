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
# Helpers for the docker build and push scripts. Source this file from the
# repository root. The registry settings are documented in system.env.sample.

SYSTEM_ENV_VARS=(PROVIDER_REGISTRY SERVER_REGISTRY DOCKER_USER DOCKER_TOKEN)

# Loads system.env if it exists. A value that is already set in the
# environment (e.g., by CI) takes precedence over the file.
load_system_env() {
    local env_file="system.env"
    if [ ! -f "${env_file}" ]; then
        return 0
    fi
    local saved=()
    local var
    for var in "${SYSTEM_ENV_VARS[@]}"; do
        saved+=("${var}=${!var}")
    done
    # shellcheck source=/dev/null
    source "${env_file}"
    local entry
    for entry in "${saved[@]}"; do
        if [ -n "${entry#*=}" ]; then
            printf -v "${entry%%=*}" '%s' "${entry#*=}"
        fi
    done
}

# Prints the registry prefix with exactly one trailing slash, or nothing if
# the prefix is empty.
registry_prefix() {
    local registry="${1%/}"
    if [ -n "${registry}" ]; then
        echo "${registry}/"
    fi
}

# Exits with an error if the named registry variable is not set.
require_registry() {
    local name="$1"
    if [ -z "${!name}" ]; then
        echo "${name} is not set. set it in system.env (see system.env.sample)" \
            "or in the environment to say where the images are pushed" >&2
        exit 1
    fi
}

# Prints the host part of an image prefix the way docker interprets it
# (nothing for Docker Hub).
registry_host() {
    local registry="${1%/}"
    local first="${registry%%/*}"
    if [[ "${registry}" == */* ]] \
            && [[ "${first}" == *.* || "${first}" == *:* \
                || "${first}" == "localhost" ]]; then
        echo "${first}"
    elif [[ "${registry}" != */* ]] \
            && [[ "${registry}" == *.* || "${registry}" == *:* ]]; then
        echo "${registry}"
    fi
}

# Logs in to the registry of the given image prefix if DOCKER_USER and
# DOCKER_TOKEN are set. Otherwise, an existing docker login is used.
docker_login_for() {
    local host
    host="$(registry_host "$1")"
    if [ -z "${DOCKER_USER}" ] || [ -z "${DOCKER_TOKEN}" ]; then
        echo "DOCKER_USER or DOCKER_TOKEN not set." \
            "using the existing docker login for ${host:-Docker Hub}"
        return 0
    fi
    if [ -n "${host}" ]; then
        echo "${DOCKER_TOKEN}" \
            | docker login "${host}" --username "${DOCKER_USER}" --password-stdin
    else
        echo "${DOCKER_TOKEN}" \
            | docker login --username "${DOCKER_USER}" --password-stdin
    fi
}
