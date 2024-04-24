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
