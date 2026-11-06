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
import json
import os
from typing import cast, TypedDict

from redipy import RedisConfig
from scattermind.system.io import open_reads, open_writes
from scattermind.system.session.loader import SessionStoreModule

from swai_server.env import envload_int, envload_path, envload_str
from swai_server.system.user.loader import UserManagerModule


Config = TypedDict('Config', {
    "task_queue": RedisConfig,
    "session_store": SessionStoreModule,
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
        "task_queue": {
            "host": "INVALID",
            "passwd": "",
            "path": "swai_server/tasks/redis",
            "port": 6379,
            "prefix": "tasks",
        },
        "session_store": {
            "user": {
                "name": "redis",
                "cfg": {
                    "host": "INVALID",
                    "passwd": "",
                    "path": "swai_server/session/redis",
                    "port": 6379,
                    "prefix": "sessions",
                },
            },
            "key_value": {
                "name": "redis",
                "cfg": {
                    "host": "INVALID",
                    "passwd": "",
                    "path": "swai_server/session/redis",
                    "port": 6379,
                    "prefix": "sessions",
                },
            },
            "blob": {
                "name": "disk",
                "cfg": {
                    "host": "INVALID",
                    "passwd": "",
                    "path": "swai_server/session/redis",
                    "port": 6379,
                    "prefix": "sessions",
                },
                "disk_path": "swai_server/session/disk",
            },
            "cache_path": "swai_server/session/cache",
            "is_shared": False,
        },
        "user_mng": {
            "name": "redis",
            "cfg": {
                "host": "INVALID",
                "passwd": "",
                "path": "swai_server/users/redis",
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


def select_user_store(config: Config) -> Config:
    """
    Applies the `USER_STORE` setting. It selects the user store without
    changing the config file (which is part of the docker image): "postgres"
    keeps the accounts in Postgres (connection from the PG* settings) and
    "redis" or no value keeps the user store of the config file.

    Args:
        config (Config): The configuration.

    Returns:
        Config: The configuration with the selected user store.
    """
    user_store = envload_str("USER_STORE", default="").strip().lower()
    if not user_store or user_store == config["user_mng"]["name"]:
        return config
    if user_store == "postgres":
        return {
            **config,
            "user_mng": {
                "name": "postgres",
            },
        }
    raise ValueError(
        f"USER_STORE={user_store} is not supported: use 'postgres' or set "
        "the user store in the config file")


def get_config() -> Config:
    global CONFIG  # pylint: disable=global-statement

    if CONFIG is not None:
        return CONFIG
    CONFIG = select_user_store(load_config())
    return CONFIG


def load_config() -> Config:
    config_path = get_config_path()
    if config_path == "-":
        print("loading config from env")
        session_root = envload_path("SESSION_PATH")
        return {
            "task_queue": {
                "host": envload_str("REDIS_HOST"),
                "passwd": envload_str("REDIS_PW"),
                "path": envload_path("REDIS_PATH"),
                "port": envload_int("REDIS_PORT"),
                "prefix": envload_str("REDIS_PREFIX"),
            },
            "session_store": {
                "user": {
                    "name": "redis",
                    "cfg": {
                        "host": envload_str("REDIS_HOST"),
                        "passwd": envload_str("REDIS_PW"),
                        "path": envload_path("REDIS_PATH"),
                        "port": envload_int("REDIS_PORT"),
                        "prefix": envload_str("REDIS_PREFIX"),
                    },
                },
                "key_value": {
                    "name": "redis",
                    "cfg": {
                        "host": envload_str("REDIS_HOST"),
                        "passwd": envload_str("REDIS_PW"),
                        "path": envload_path("REDIS_PATH"),
                        "port": envload_int("REDIS_PORT"),
                        "prefix": envload_str("REDIS_PREFIX"),
                    },
                },
                "blob": {
                    "name": "disk",
                    "cfg": {
                        "host": envload_str("REDIS_HOST"),
                        "passwd": envload_str("REDIS_PW"),
                        "path": envload_path("REDIS_PATH"),
                        "port": envload_int("REDIS_PORT"),
                        "prefix": envload_str("REDIS_PREFIX"),
                    },
                    "disk_path": os.path.join(session_root, "disk"),
                },
                "cache_path": os.path.join(session_root, "cache"),
                "is_shared": False,
            },
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
    print(f"loading config file: {config_path}")
    if not os.path.exists(config_path):
        create_config_and_err(config_path)
    with open_reads(config_path) as fin:
        config = cast(Config, json.load(fin))
    if not config:
        create_config_and_err(config_path)
    return config
