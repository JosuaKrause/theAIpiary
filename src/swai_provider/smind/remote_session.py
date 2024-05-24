import io
import time
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from typing import IO, TypeVar

import requests
from scattermind.system.base import L_REMOTE, Locality, SessionId, UserId
from scattermind.system.names import UName
from scattermind.system.session.session import Session, SessionStore

from swai.server_response_types import (
    WorkerBlobHashResponse,
    WorkerBlobListResponse,
    WorkerKeysResponse,
    WorkerSessionListResponse,
    WorkerSessionResponse,
    WorkerSignalResponse,
    WorkerUploadResponse,
    WorkerUserResponse,
    WorkerValueResponse,
)
from swai.system.user.manager import WorkerToken
from swai_provider.env import envload_str


T = TypeVar('T')


class RemoteSessionStore(SessionStore):
    def __init__(
            self,
            cache_path: str,
            is_shared: bool) -> None:
        # FIXME: use timeouts
        super().__init__(cache_path=cache_path, is_shared=is_shared)
        self._name = UName(envload_str("SWAI_USER"))
        self._worker_token: WorkerToken = envload_str("SWAI_WORKER_TOKEN")
        self._api_url = envload_str("SWAI_API_URL")
        self._api = requests.Session()

    @staticmethod
    def locality() -> Locality:
        return L_REMOTE

    def _url(self, path: str) -> str:
        return f"{self._api_url}/smind{path}"

    def _json(self) -> dict[str, str | int | float | list[str] | None]:
        return {
            "name": self._name.get(),
            "worker_token": self._worker_token,
        }

    def register_session(self, user_id: UserId, session_id: SessionId) -> None:
        obj = self._json()
        obj["user_id"] = user_id.to_parseable()
        obj["session"] = session_id.to_parseable()
        resp = self._api.put(self._url("/session"), json=obj)
        resp.raise_for_status()
        res: WorkerSessionResponse = resp.json()
        assert res["ok"]

    def get_sessions(self, user_id: UserId) -> Iterable[Session]:
        obj = self._json()
        obj["user_id"] = user_id.to_parseable()
        resp = self._api.post(self._url("/session"), json=obj)
        resp.raise_for_status()
        res: WorkerSessionListResponse = resp.json()
        yield from (
            self.get_session(SessionId.parse(session))
            for session in res["sessions"]
        )

    def get_user(self, session_id: SessionId) -> UserId | None:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        resp = self._api.post(self._url("/user"), json=obj)
        resp.raise_for_status()
        res: WorkerUserResponse = resp.json()
        user_id_str = res["user_id"]
        if user_id_str is None:
            return None
        return UserId.parse(user_id_str)

    def set_value(
            self,
            session_id: SessionId,
            key: str,
            index: int,
            value: str) -> None:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        obj["op"] = "set"
        obj["key"] = key
        obj["index"] = index
        obj["value"] = value
        resp = self._api.post(self._url("/value"), json=obj)
        resp.raise_for_status()
        res: WorkerValueResponse = resp.json()
        assert res["success"]

    def push_value(self, session_id: SessionId, key: str, value: str) -> None:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        obj["op"] = "push"
        obj["key"] = key
        obj["value"] = value
        resp = self._api.post(self._url("/value"), json=obj)
        resp.raise_for_status()
        res: WorkerValueResponse = resp.json()
        assert res["success"]

    def pop_value(self, session_id: SessionId, key: str) -> str | None:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        obj["op"] = "pop"
        obj["key"] = key
        resp = self._api.post(self._url("/value"), json=obj)
        resp.raise_for_status()
        res: WorkerValueResponse = resp.json()
        assert res["success"]
        return res["value"]

    def get_value(
            self, session_id: SessionId, key: str, index: int) -> str | None:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        obj["op"] = "get"
        obj["key"] = key
        obj["index"] = index
        resp = self._api.post(self._url("/value"), json=obj)
        resp.raise_for_status()
        res: WorkerValueResponse = resp.json()
        assert res["success"]
        return res["value"]

    def get_length(self, session_id: SessionId, key: str) -> int:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        obj["op"] = "length"
        obj["key"] = key
        resp = self._api.post(self._url("/value"), json=obj)
        resp.raise_for_status()
        res: WorkerValueResponse = resp.json()
        assert res["success"]
        return res["length"]

    def get_keys(self, session_id: SessionId) -> list[str]:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        resp = self._api.post(self._url("/keys"), json=obj)
        resp.raise_for_status()
        res: WorkerKeysResponse = resp.json()
        return res["keys"]

    def notify_signal(self, session_id: SessionId, key: str) -> None:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        obj["key"] = key
        resp = self._api.post(self._url("/signal"), json=obj)
        resp.raise_for_status()
        res: WorkerSignalResponse = resp.json()
        assert res["signal"]

    def wait_for_signal(
            self,
            session_id: SessionId,
            key: str,
            condition: Callable[[], T],
            *,
            timeout: float) -> T | None:
        start_time = time.monotonic()
        while True:
            value = condition()
            if bool(value):
                return value
            time_passed = time.monotonic() - start_time
            if time_passed >= timeout:
                return None
            obj = self._json()
            obj["session"] = session_id.to_parseable()
            obj["key"] = key
            obj["timeout"] = timeout - time_passed
            resp = self._api.post(self._url("/signal"), json=obj)
            resp.raise_for_status()
            res: WorkerSignalResponse = resp.json()
            assert "signal" in res

    @contextmanager
    def open_blob_write(
            self, session_id: SessionId, name: str) -> Iterator[IO[bytes]]:
        bout = io.BytesIO()
        yield bout
        bout.seek(0, io.SEEK_SET)
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        obj["blob"] = name
        resp = self._api.put(
            self._url("/blob"),
            data=obj,
            files={
                "blob": (
                    "blob",
                    bout,
                    "application/octet-stream",
                ),
            })
        resp.raise_for_status()
        res: WorkerUploadResponse = resp.json()
        assert res["done"]

    @contextmanager
    def open_blob_read(
            self, session_id: SessionId, name: str) -> Iterator[IO[bytes]]:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        obj["blob"] = name
        resp = self._api.post(self._url("/blob"), json=obj)
        resp.raise_for_status()
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
        resp = self._api.post(self._url("/hash"), json=obj)
        resp.raise_for_status()
        res: WorkerBlobHashResponse = resp.json()
        return res["blob_hashes"]

    def blob_list(self, session_id: SessionId) -> list[str]:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        resp = self._api.post(self._url("/list"), json=obj)
        resp.raise_for_status()
        res: WorkerBlobListResponse = resp.json()
        return res["blobs"]

    def blob_remove(self, session_id: SessionId, names: list[str]) -> None:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        obj["blobs"] = sorted(set(names))
        resp = self._api.delete(self._url("/blob"), json=obj)
        resp.raise_for_status()
        res: WorkerUploadResponse = resp.json()
        assert res["done"]

    def remove(self, session_id: SessionId) -> None:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        resp = self._api.delete(self._url("/session"), json=obj)
        resp.raise_for_status()
        res: WorkerSessionResponse = resp.json()
        assert res["ok"]
