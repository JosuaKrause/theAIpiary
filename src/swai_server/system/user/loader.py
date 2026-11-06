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
from typing import Literal, NotRequired, TypedDict

from redipy import RedisConfig
from scattermind.system.names import UName

from swai_server.system.user.manager import RawPassword, UserManager


RedisUserManagerModule = TypedDict('RedisUserManagerModule', {
    "name": Literal["redis"],
    "cfg": RedisConfig,
})


# NOTE: the connection settings are read from the PG* environment variables
# (see db_config_from_env) so that the password is kept out of the config
# file
PostgresUserManagerModule = TypedDict('PostgresUserManagerModule', {
    "name": Literal["postgres"],
    "schema": NotRequired[str],
})


UserManagerModule = RedisUserManagerModule | PostgresUserManagerModule


def load_user_manager(
        module: UserManagerModule,
        *,
        admin_email: UName | None,
        admin_pw: RawPassword | None) -> UserManager:
    # pylint: disable=import-outside-toplevel
    if module["name"] == "redis":
        from swai_server.system.user.redis import RedisUserManager
        return RedisUserManager(
            cfg=module["cfg"], admin_email=admin_email, admin_pw=admin_pw)
    if module["name"] == "postgres":
        from swai_server.system.db.db import (
            create_db_engine,
            db_config_from_env,
            get_db_url,
        )
        from swai_server.system.user.db import DBUserManager
        db_config = db_config_from_env(schema=module.get("schema"))
        engine = create_db_engine(
            get_db_url(db_config), schema=db_config["schema"])
        return DBUserManager(
            engine=engine,
            schema=db_config["schema"],
            admin_email=admin_email,
            admin_pw=admin_pw)
    raise ValueError(f"unknown session store: {module['name']}")
