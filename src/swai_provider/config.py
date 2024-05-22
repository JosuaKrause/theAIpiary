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
import json
import os
from typing import cast, TypedDict

from scattermind.system.io import open_reads, open_writes

from swai.system.user.loader import UserManagerModule
from swai_provider.env import envload_int, envload_path, envload_str


Config = TypedDict('Config', {
    "smind": str,
    "graphs": str,
    "user_mng": UserManagerModule,
})


CONFIG: Config | None = None
CONFIG_PATH: str | None = None


def get_config_path() -> str:
    global CONFIG_PATH  # pylint: disable=global-statement

    if CONFIG_PATH is None:
        CONFIG_PATH = envload_path("CONFIG_PATH", default="config.json")
    return CONFIG_PATH


def config_template() -> Config:
    return {
        "smind": "smind-config.json",
        "graphs": "graphs/",
        "user_mng": {
            "name": "redis",
            "cfg": {
                "host": "INVALID",
                "passwd": "",
                "path": "users",
                "port": 6379,
                "prefix": "users",
            },
        },
    }


def create_config_and_err(config_path: str) -> None:
    with open_writes(config_path) as fout:
        print(
            json.dumps(config_template(), indent=4, sort_keys=True),
            file=fout)
    raise ValueError(
        "config file missing. "
        f"new file was created at '{config_path}'. "
        "please correct values in file and run again")


def get_config() -> Config:
    global CONFIG  # pylint: disable=global-statement

    if CONFIG is not None:
        return CONFIG
    config_path = get_config_path()
    if config_path == "-":
        print("loading config from env")
        CONFIG = {
            "smind": envload_path("SMIND_CFG"),
            "graphs": envload_path("GRAPH_PATH"),
            "user_mng": {
                "name": "redis",
                "cfg": {
                    "host": envload_str("REDIS_HOST"),
                    "passwd": envload_str("REDIS_PW"),
                    "path": envload_path("REDIS_PATH"),
                    "port": envload_int("REDIS_PORT"),
                    "prefix": envload_str("REDIS_PREFIX"),
                },
            },
        }
    else:
        print(f"loading config file: {config_path}")
        if not os.path.exists(config_path):
            create_config_and_err(config_path)
        with open_reads(config_path) as fin:
            config = cast(Config, json.load(fin))
            if not config:
                create_config_and_err(config_path)
            CONFIG = config
    return CONFIG
