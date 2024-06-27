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
import contextlib
import inspect
import sys
import threading
import urllib
from collections.abc import Iterator
from typing import Any, TYPE_CHECKING, TypedDict

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session


if TYPE_CHECKING:
    from swai_server.system.db.base import Base


VERBOSE = False


DBConfig = TypedDict('DBConfig', {
    "dialect": str,
    "host": str,
    "port": int,
    "user": str,
    "passwd": str,
    "dbname": str,
    "schema": str,
})


EngineKey = tuple[str, str, int, str, str, str]


def get_engine_key(config: DBConfig) -> EngineKey:
    return (
        config["dialect"],
        config["host"],
        config["port"],
        config["user"],
        config["dbname"],
        config["schema"],
    )


LOCK = threading.RLock()
ENGINES: dict[EngineKey, sa.engine.Engine] = {}


def get_engine(config: DBConfig) -> sa.engine.Engine:
    key = get_engine_key(config)
    res = ENGINES.get(key)
    if res is not None:
        return res
    with LOCK:
        res = ENGINES.get(key)
        if res is not None:
            return res
        dialect = config["dialect"]
        if dialect != "postgresql":
            print(
                "dialects other than 'postgresql' are not supported. "
                "continue at your own risk", file=sys.stderr)
        user = urllib.parse.quote_plus(config["user"])
        passwd = urllib.parse.quote_plus(config["passwd"])
        host = config["host"]
        port = config["port"]
        dbname = config["dbname"]
        res = sa.create_engine(
            f"{dialect}://{user}:{passwd}@{host}:{port}/{dbname}",
            echo=VERBOSE)
        res = res.execution_options(
            schema_translate_map={None: config["schema"]})
        ENGINES[key] = res
    return res


class DBConnector:
    def __init__(self, config: DBConfig) -> None:
        self._engine = get_engine(config)
        self._namespaces: dict[str, int] = {}
        self._modules: dict[str, int] = {}
        self._schema = config["schema"]

    def table_exists(self, table: type['Base']) -> bool:
        return sa.inspect(self._engine).has_table(
            table.__table__.name, schema=self._schema)

    def create_tables(self, tables: list[type['Base']]) -> None:
        # pylint: disable=import-outside-toplevel
        from swai_server.system.db.base import Base

        Base.metadata.create_all(
            self._engine,
            tables=[table.__table__ for table in tables],
            checkfirst=True)

    @staticmethod
    def all_tables() -> list[type['Base']]:
        # pylint: disable=import-outside-toplevel
        from swai_server.system.db.base import Base

        return [
            clz
            for _, clz in
            inspect.getmembers(sys.modules["system.db.base"], inspect.isclass)
            if clz is not Base and issubclass(clz, Base)
        ]

    def is_init(self) -> bool:
        return all((self.table_exists(clz) for clz in self.all_tables()))

    def init_db(self) -> None:
        if self.is_init():
            return
        self.create_tables(self.all_tables())

    def get_engine(self) -> sa.engine.Engine:
        return self._engine

    @contextlib.contextmanager
    def get_connection(self) -> Iterator[sa.engine.Connection]:
        with self._engine.connect() as conn:
            yield conn

    @contextlib.contextmanager
    def get_session(self, autocommit: bool = True) -> Iterator[Session]:
        success = False
        with Session(self._engine) as session:
            try:
                yield session
                success = True
            finally:
                if autocommit:
                    if success:
                        session.commit()
                    else:
                        session.rollback()

    def upsert(self, table: type['Base']) -> Any:
        return pg_insert(table)
