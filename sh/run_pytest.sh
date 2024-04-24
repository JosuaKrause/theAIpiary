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

PYTHON="${PYTHON:-python}"
RESULT_FNAME="${RESULT_FNAME:-results.xml}"
IFS=',' read -a FILE_INFO <<< "$1"
FILES=("${FILE_INFO[@]}")
export USER_FILEPATH=./userdata

coverage erase

find . -type d \( \
    -path './venv' -o \
    -path './.*' -o \
    -path './userdata' \
    \) -prune -o \
    -name '*.py' \
    -exec ${PYTHON} -m compileall -q -j 0 {} +

run_test() {
    ${PYTHON} -m pytest \
        -xvv --full-trace \
        --junitxml="test-results/parts/result${2}.xml" \
        --cov --cov-append \
        $1
}
export -f run_test

if ! [ -z "${FILES}" ]; then
    IDX=0
    echo "${FILES[@]}"
    for CUR_TEST in "${FILES[@]}"; do
        run_test $CUR_TEST $IDX
        IDX=$((IDX+1))
    done
else
    IDX=0
    for CUR in $(find 'test' -type d \( \
            -path 'test/data' -o \
            -path 'test/__pycache__' \
            \) -prune -o \( \
            -name '*.py' -and \
            -name 'test_*' \
            \) | \
            grep -E '.*\.py' | \
            sort -sf); do
        run_test ${CUR} $IDX
        IDX=$((IDX+1))
    done
fi
${PYTHON} -m test merge_results --dir test-results --out-fname ${RESULT_FNAME}
rm -r test-results/parts

coverage xml -o coverage/reports/xml_report.xml
coverage html -d coverage/reports/html_report
