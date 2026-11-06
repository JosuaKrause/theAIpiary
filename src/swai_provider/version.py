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
