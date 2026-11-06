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
import os
from typing import Literal

from scattermind.system.util import to_bool


EnvPath = Literal[
    "CONFIG_PATH",
    "GRAPH_PATH",
    "HISTORY_PATH",
    "PUBLIC_PATH",
    "SMIND_CFG",
    "VERSION_PATH",
]
EnvStr = Literal[
    "AIPIARY_API_URL",
    "AIPIARY_USER",
    "AIPIARY_WORKER_TOKEN",
    "HOST",
    "DEVICE_ID",
]
EnvInt = Literal[
    "PORT",
    "REDIS_PORT",
]
EnvBool = Literal["!"]  # FIXME: placeholder for actual env names


def _envload(key: str, default: str | None) -> str:
    res = os.environ.get(key)
    if res is not None:
        return res
    if default is not None:
        return default
    raise ValueError(f"env {key} must be set!")


def envload_str(key: EnvStr, *, default: str | None = None) -> str:
    return _envload(key, default)


def envload_path(key: EnvPath, *, default: str | None = None) -> str:
    return _envload(key, default)


def envload_int(key: EnvInt, *, default: int | None = None) -> int:
    return int(_envload(key, f"{default}"))


def envload_bool(key: EnvBool, *, default: bool | None = None) -> bool:
    return to_bool(_envload(key, f"{default}"))
