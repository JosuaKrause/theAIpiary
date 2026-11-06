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

FLAG=$1

CUR_VERSION=$(git tag --merged | sort -rV | head -n 1)

if [ "${FLAG}" == '--current' ]; then
    echo "${CUR_VERSION}"
    exit 0
fi

if [ ! -z "${FLAG}" ]; then
    echo "$0 [--current]"
    echo "prints the next version (or current version if specified) and exits"
    exit 1
fi

# version must match either of:
# v<MAJOR_VERSION>.<MINOR_VERSION>.<PATCH_VERSION>rc<RC_VERSION>
# v<MAJOR_VERSION>.<MINOR_VERSION>.<PATCH_VERSION>

MAJOR_VERSION=$(echo "${CUR_VERSION}" | awk -F'rc' '{print $1}' | awk -F'v' '{print $2}' | awk -F'.' '{print $1}')
MINOR_VERSION=$(echo "${CUR_VERSION}" | awk -F'rc' '{print $1}' | awk -F'v' '{print $2}' | awk -F'.' '{print $2}')
PATCH_VERSION=$(echo "${CUR_VERSION}" | awk -F'rc' '{print $1}' | awk -F'v' '{print $2}' | awk -F'.' '{print $3}')
RC_VERSION=$(echo "${CUR_VERSION}" | awk -F'rc' '{print $2}')

# next version on minor version only
MINOR_VERSION=$((MINOR_VERSION + 1))
PATCH_VERSION=0
RC_VERSION=0

if [ -n $RC_VERSION -a $RC_VERSION -ne 0 ]
then
    echo "v${MAJOR_VERSION}.${MINOR_VERSION}.${PATCH_VERSION}rc${RC_VERSION}"
else
    echo "v${MAJOR_VERSION}.${MINOR_VERSION}.${PATCH_VERSION}"
fi
