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
from scattermind.system.util import file_hash_size, short_hash_size
from sqlalchemy.orm import registry
from sqlalchemy.orm.decl_api import DeclarativeMeta


SESSION_ID_LENGTH = SessionId.length()
FILE_HASH_SIZE = file_hash_size()
CAPABILITY_LENGTH = 40
MODEL_TYPE_LENGTH = 20
USER_HASH_LENGTH = short_hash_size()


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


class User(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "user"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    user_hash = sa.Column(sa.UUID, nullable=False, unique=True)
    name = sa.Column(sa.Text(), nullable=False)
    email = sa.Column(sa.Text(), nullable=False)
    password = sa.Column(sa.Text(), nullable=True)
    user_key = sa.Column(sa.Text(), nullable=True)
    reset_token = sa.Column(sa.UUID, nullable=True)


class UserSession(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "user"

    user_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            User.id,
            onupdate="CASCADE",
            ondelete="CASCADE"),
        nullable=False,
        primary_key=True)
    session_id = sa.Column(sa.UUID, nullable=False, primary_key=True)
    expire = sa.Column(sa.DateTime(timezone=True), nullable=True)


class Capabilities(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "capabilities"

    user_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            User.id,
            onupdate="CASCADE",
            ondelete="CASCADE"),
        nullable=False,
        primary_key=True)
    capability = sa.Column(
        sa.String(CAPABILITY_LENGTH),
        nullable=False,
        primary_key=True)


class Worker(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "worker"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    name = sa.Column(sa.Text(), nullable=False)
    owner_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            User.id,
            onupdate="CASCADE",
            ondelete="CASCADE"),
        nullable=False)


class Hive(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "hive"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    name = sa.Column(sa.Text(), nullable=False, unique=True)
    owner_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            User.id,
            onupdate="CASCADE",
            ondelete="CASCADE"),
        nullable=False)
    hive_key = sa.Column(sa.Text(), nullable=True)
    hive_access = sa.Column(sa.UUID, nullable=False)


class WorkerHive(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "worker_hive"

    worker_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            Worker.id,
            onupdate="CASCADE",
            ondelete="CASCADE"),
        nullable=False,
        primary_key=True)
    hive_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            Hive.id,
            onupdate="CASCADE",
            ondelete="CASCADE"),
        nullable=False,
        primary_key=True)


class Model(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "model"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    name = sa.Column(sa.Text(), nullable=False)
    modelhash = sa.Column(sa.String(FILE_HASH_SIZE), nullable=False)
    modeltype = sa.Column(sa.String(MODEL_TYPE_LENGTH), nullable=False)
    hive_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            Hive.id,
            onupdate="CASCADE",
            ondelete="CASCADE"),
        nullable=False)


class ModelSession(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "model_session"

    id = sa.Column(sa.String(SESSION_ID_LENGTH), primary_key=True)
    user_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            User.id,
            onupdate="CASCADE",
            ondelete="CASCADE"),
        nullable=False)
    model_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            Model.id,
            onupdate="CASCADE",
            ondelete="CASCADE"),
        nullable=False)
    description = sa.Column(sa.Text(), nullable=True)


class Blob(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "blob"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    session = sa.Column(
        sa.String(SESSION_ID_LENGTH),
        sa.ForeignKey(
            ModelSession.id,
            onupdate="CASCADE",
            ondelete="CASCADE"),
        nullable=False)
    path = sa.Column(sa.Text(), nullable=False)
    filehash = sa.Column(sa.String(FILE_HASH_SIZE), nullable=False)
    access_last = sa.Column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now())  # pylint: disable=not-callable
