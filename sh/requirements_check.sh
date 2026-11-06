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

PYTHON="${PYTHON:-python}"
FILE=${1:-requirements.txt}

TMP=$(mktemp tmp.XXXXXX)

cat ${FILE} | sed -E 's/(\[[a-z]+\])?//g' > ${TMP}

${PYTHON} -m pip freeze | sort -sf | grep -i -E "^($(cat ${TMP} | sed -E 's/[=~>]=.+//g' | perl -p -e 'chomp if eof' | tr '\n' '|'))=" | diff -U 0 ${TMP} -

rm ${TMP}

echo "NOTE: '+' is your local version and '-' is the version in ${FILE}" 1>&2
