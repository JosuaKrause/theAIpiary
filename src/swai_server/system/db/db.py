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
"""Connecting to Postgres."""
from typing import TypedDict

import sqlalchemy as sa

from swai_server.env import envload_int, envload_str


DEFAULT_SCHEMA = "public"


DBConfig = TypedDict('DBConfig', {
    "host": str,
    "port": int,
    "user": str,
    "passwd": str,
    "dbname": str,
    "schema": str,
})


def db_config_from_env(*, schema: str | None = None) -> DBConfig:
    """
    Reads the connection settings from the standard libpq variables
    `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, and `PGDATABASE`.

    Args:
        schema (str | None, optional): The schema that holds the tables.
            Defaults to "public".

    Returns:
        DBConfig: The connection settings.
    """
    return {
        "host": envload_str("PGHOST"),
        "port": envload_int("PGPORT", default=5432),
        "user": envload_str("PGUSER"),
        "passwd": envload_str("PGPASSWORD", default=""),
        "dbname": envload_str("PGDATABASE"),
        "schema": DEFAULT_SCHEMA if not schema else schema,
    }


def get_db_url(config: DBConfig) -> sa.URL:
    """
    The connection URL for the given settings.

    Args:
        config (DBConfig): The connection settings.

    Returns:
        sa.URL: The URL.
    """
    return sa.URL.create(
        "postgresql+psycopg2",
        username=config["user"],
        password=config["passwd"] or None,
        host=config["host"],
        port=config["port"],
        database=config["dbname"])


def create_db_engine(url: sa.URL | str, *, schema: str) -> sa.Engine:
    """
    Creates an engine whose tables (defined without a schema) live in the
    given schema.

    Args:
        url (sa.URL | str): The connection URL.
        schema (str): The schema.

    Returns:
        sa.Engine: The engine.
    """
    engine = sa.create_engine(url, pool_pre_ping=True)
    return engine.execution_options(schema_translate_map={None: schema})
