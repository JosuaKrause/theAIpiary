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
import io
import uuid
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from typing import IO, TypeVar

import requests
from scattermind.system.base import L_REMOTE, Locality, SessionId
from scattermind.system.names import UName
from scattermind.system.session.session import SessionBlob

from swai.auth import get_authorization
from swai.server_response_types import (
    WorkerBlobHashResponse,
    WorkerBlobListResponse,
    WorkerUploadResponse,
)
from swai.system.base import REQUEST_TIMEOUT, retry_on_disconnect
from swai.system.user import WorkerToken
from swai_provider.env import envload_str


T = TypeVar('T')


class RemoteSessionBlob(SessionBlob):
    def __init__(self) -> None:
        self._name = UName(envload_str("AIPIARY_USER"))
        self._worker_token: WorkerToken = envload_str("AIPIARY_WORKER_TOKEN")
        self._api_url = envload_str("AIPIARY_API_URL").removesuffix("/")
        self._api = requests.Session()

    def locality(self) -> Locality:
        return L_REMOTE

    def _url(self, path: str) -> str:
        return f"{self._api_url}/api/smind{path}"

    def _json(self) -> dict[str, str | int | float | list[str] | None]:
        return {}

    def _headers(self) -> dict[str, str]:
        return {
            "authorization": get_authorization(self._name, self._worker_token),
        }

    @contextmanager
    def open_blob_write(
            self, session_id: SessionId, name: str) -> Iterator[IO[bytes]]:
        bout = io.BytesIO()
        yield bout
        bout.seek(0, io.SEEK_SET)
        upload_id = uuid.uuid4().hex
        chunk_size = 1024 * 10  # 10kiB
        # FIXME: parallelize and use the missing field

        def send_chunk(
                chunk_ix: int, bchunk: IO[bytes], *, complete: bool) -> None:
            obj = self._json()
            obj["session"] = session_id.to_parseable()
            obj["blob"] = name
            obj["upload_id"] = upload_id
            obj["fragment"] = chunk_ix
            obj["complete"] = complete

            def put() -> requests.Response:
                # NOTE: a retry has to send the whole chunk again
                bchunk.seek(0, io.SEEK_SET)
                return self._api.put(
                    self._url("/blob"),
                    data=obj,
                    files={
                        "blob": (
                            "blob",
                            bchunk,
                            "application/octet-stream",
                        ),
                    },
                    headers=self._headers(),
                    timeout=REQUEST_TIMEOUT)

            # NOTE: a chunk is addressed by its fragment index so sending it
            # again overwrites it. the completing chunk of a multi chunk blob
            # is the exception: it assembles the blob and deletes the
            # fragments, so a repeat reports the earlier fragments as missing
            resp = retry_on_disconnect(
                put, idempotent=not complete or chunk_ix == 0)
            res: WorkerUploadResponse = resp.json()
            assert res["done"]
            assert not res["missing"]

        ix = 0
        complete = False
        bchunk: io.BytesIO | None = None
        while True:
            cur = bout.read(chunk_size)
            if not cur:
                complete = True
            if bchunk is not None:
                send_chunk(ix, bchunk, complete=complete)
                ix += 1
            if complete:
                break
            bchunk = io.BytesIO(cur)
        if bchunk is None:
            send_chunk(ix, io.BytesIO(), complete=True)

    @contextmanager
    def open_blob_read(
            self, session_id: SessionId, name: str) -> Iterator[IO[bytes]]:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        obj["blob"] = name
        resp = retry_on_disconnect(
            lambda: self._api.post(
                self._url("/blob"),
                json=obj,
                headers=self._headers(),
                timeout=REQUEST_TIMEOUT),
            idempotent=True)
        bout = io.BytesIO(resp.content)
        try:
            yield bout
        finally:
            bout.close()

    def blob_hash(
            self,
            session_id: SessionId,
            names: Iterable[str]) -> dict[str, str]:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        obj["blobs"] = sorted(set(names))
        resp = retry_on_disconnect(
            lambda: self._api.post(
                self._url("/hash"),
                json=obj,
                headers=self._headers(),
                timeout=REQUEST_TIMEOUT),
            idempotent=True)
        res: WorkerBlobHashResponse = resp.json()
        return res["blob_hashes"]

    def blob_list(self, session_id: SessionId) -> list[str]:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        resp = retry_on_disconnect(
            lambda: self._api.post(
                self._url("/list"),
                json=obj,
                headers=self._headers(),
                timeout=REQUEST_TIMEOUT),
            idempotent=True)
        res: WorkerBlobListResponse = resp.json()
        return res["blobs"]

    def blob_remove(self, session_id: SessionId, names: list[str]) -> None:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        obj["blobs"] = sorted(set(names))
        resp = retry_on_disconnect(
            lambda: self._api.delete(
                self._url("/blob"),
                json=obj,
                headers=self._headers(),
                timeout=REQUEST_TIMEOUT),
            idempotent=True)
        res: WorkerUploadResponse = resp.json()
        assert res["done"]

    def remove(self, session_id: SessionId) -> None:
        # NOTE: handled by RemoteSessionUser
        pass
