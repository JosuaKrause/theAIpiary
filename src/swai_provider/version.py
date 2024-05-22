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
import subprocess
from typing import Literal

from scattermind.system.io import open_reads
from scattermind.system.util import get_time_str

from swai_provider.env import envload_path


VERSION_NAME: str | None = None
VERSION_HASH: str | None = None
VERSION_DATE: str | None = None


def simple_call(cmd: list[str]) -> str | None:
    try:
        return subprocess.check_output(
            cmd, stderr=subprocess.STDOUT).decode("utf-8")
    except subprocess.CalledProcessError:
        return None


VersionResult = Literal["name", "hash", "date"]


def get_version(version_result: VersionResult) -> str:
    global VERSION_NAME  # pylint: disable=global-statement
    global VERSION_HASH  # pylint: disable=global-statement
    global VERSION_DATE  # pylint: disable=global-statement

    if VERSION_NAME is None or VERSION_HASH is None or VERSION_DATE is None:
        VERSION_NAME = simple_call(["make", "-s", "name"])
        if VERSION_NAME is None:
            version_path = envload_path("VERSION_PATH", default="version.txt")
            with open_reads(version_path) as fin:
                VERSION_NAME = fin.readline().strip()
                VERSION_HASH = fin.readline().strip()
                VERSION_DATE = fin.readline().strip()
        else:
            VERSION_NAME = f"LOCAL {VERSION_NAME}".strip()
            VERSION_HASH = simple_call(["make", "-s", "commit"])
            if VERSION_HASH is None:
                VERSION_HASH = "ERROR"
            else:
                VERSION_HASH = VERSION_HASH.strip()
            VERSION_DATE = get_time_str()
    if version_result == "name":
        return VERSION_NAME
    if version_result == "hash":
        return VERSION_HASH
    if version_result == "date":
        return VERSION_DATE
    raise ValueError(f"invalid version result: {version_result}")
