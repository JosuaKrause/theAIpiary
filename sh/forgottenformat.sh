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

ANY_DOUBLE="([^\\\\\"]|\\\\\")*"
ANY_SINGLE="([^\\\\']|\\\\')*"
IS_CURLY="([{][^{]|[^}][}])"
EAT_DOUBLE="\"${ANY_DOUBLE}\""
EAT_SINGLE="'${ANY_SINGLE}'"
EAT_STRINGS="^([^\"'#]|${EAT_DOUBLE}|${EAT_SINGLE})*"

INVALID_F_DOUBLE="f\"([^\\\\\"}{]|\\\\\")*\""
INVALID_F_SINGLE="f'([^\\\\'}{]|\\\\')*'"
INVALIDS="${INVALID_F_DOUBLE}|${INVALID_F_SINGLE}"
NO_F_DOUBLE="[^rf]\"${ANY_DOUBLE}${IS_CURLY}${ANY_DOUBLE}\""  # we also allow r
NO_F_SINGLE="'${ANY_SINGLE}${IS_CURLY}${ANY_SINGLE}'"  # we disallow any curls
NO_FS="${NO_F_DOUBLE}|${NO_F_SINGLE}"

MAIN_MATCH="(${NO_FS}|${INVALIDS})"
REGEX="${EAT_STRINGS}${MAIN_MATCH}"
echo ${REGEX}

! read -r -d '' PY_FILTER <<'EOF'
import sys

stdin = sys.stdin
stdout = sys.stdout
is_triple = False
while True:
    line = stdin.readline()
    if not line:
        break
    if line.count('"""') % 2 != 0:
        is_triple = not is_triple
        continue
    if not is_triple:
        stdout.write(line)
        stdout.flush()
EOF

./sh/findpy.sh \
    | xargs grep -nE "['\"]" \
    | ${PYTHON} -c "${PY_FILTER}" \
    | grep -E "${REGEX}" \
    | grep --color=always -nE "${MAIN_MATCH}"
