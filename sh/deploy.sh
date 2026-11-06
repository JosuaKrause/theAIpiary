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

if ! make -s git-check ; then
    echo "working directory needs to be clean to deploy"
    exit 1
fi

BRANCH_MAIN=main

if [[ $(make -s branch) != "${BRANCH_MAIN}" && $(make -s branch) != v* ]]; then
    echo "must be on ${BRANCH_MAIN} or v* to deploy"
    exit 2
fi

git fetch --tags
TAG=$(make -s next-version)

if [ $(git tag --points-at HEAD) ]; then
    echo "commit is already deployed!"
    exit 3
fi

echo "deploying version: ${TAG}"
git tag "${TAG}"
git push --tags
