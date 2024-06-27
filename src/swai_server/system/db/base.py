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
import numpy as np
import sqlalchemy as sa
from psycopg2.extensions import AsIs, register_adapter
from scattermind.system.base import SessionId
from scattermind.system.util import file_hash_size
from sqlalchemy.orm import registry
from sqlalchemy.orm.decl_api import DeclarativeMeta


SESSION_ID_LENGTH = SessionId.length()
FILE_HASH_SIZE = file_hash_size()


def adapt_numpy_float64(numpy_float64: np.float64) -> AsIs:
    return AsIs(numpy_float64)


def adapt_numpy_int64(numpy_int64: np.int64) -> AsIs:
    return AsIs(numpy_int64)


register_adapter(np.float64, adapt_numpy_float64)
register_adapter(np.int64, adapt_numpy_int64)


mapper_registry = registry()


class Base(
        metaclass=DeclarativeMeta):  # pylint: disable=too-few-public-methods
    __abstract__ = True
    __table__: sa.Table

    registry = mapper_registry
    metadata = mapper_registry.metadata

    __init__ = mapper_registry.constructor


class Blob(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "blob"

    id = sa.Column(
        sa.Integer,
        nullable=False,
        unique=True,
        primary_key=True)
    session = sa.Column(
        sa.String(SESSION_ID_LENGTH),
        nullable=False)
    path = sa.Column(
        sa.Text(),
        primary_key=False,
        nullable=False)
    filehash = sa.Column(
        sa.String(FILE_HASH_SIZE),
        nullable=False)
    access_last = sa.Column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now())  # pylint: disable=not-callable
