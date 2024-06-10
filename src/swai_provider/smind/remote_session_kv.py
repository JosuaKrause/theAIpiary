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
import time
from collections.abc import Callable
from typing import TypeVar

import requests
from scattermind.system.base import L_REMOTE, Locality, SessionId
from scattermind.system.names import UName
from scattermind.system.session.session import SessionKeyValue

from swai.auth import get_authorization
from swai.server_response_types import (
    WorkerKeysResponse,
    WorkerSignalResponse,
    WorkerValueResponse,
)
from swai.system.base import retry_on_disconnect
from swai.system.user import WorkerToken
from swai_provider.env import envload_str


T = TypeVar('T')


class RemoteSessionKeyValue(SessionKeyValue):
    def __init__(self) -> None:
        # FIXME: use timeouts
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
        resp = retry_on_disconnect(lambda: self._api.post(
            self._url("/value"), json=obj, headers=self._headers()))
        res: WorkerValueResponse = resp.json()
        assert res["success"]

    def push_value(self, session_id: SessionId, key: str, value: str) -> None:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        obj["op"] = "push"
        obj["key"] = key
        obj["value"] = value
        resp = retry_on_disconnect(lambda: self._api.post(
            self._url("/value"), json=obj, headers=self._headers()))
        res: WorkerValueResponse = resp.json()
        assert res["success"]

    def pop_value(self, session_id: SessionId, key: str) -> str | None:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        obj["op"] = "pop"
        obj["key"] = key
        resp = retry_on_disconnect(lambda: self._api.post(
            self._url("/value"), json=obj, headers=self._headers()))
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
        resp = retry_on_disconnect(lambda: self._api.post(
            self._url("/value"), json=obj, headers=self._headers()))
        res: WorkerValueResponse = resp.json()
        assert res["success"]
        return res["value"]

    def get_length(self, session_id: SessionId, key: str) -> int:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        obj["op"] = "length"
        obj["key"] = key
        resp = retry_on_disconnect(lambda: self._api.post(
            self._url("/value"), json=obj, headers=self._headers()))
        res: WorkerValueResponse = resp.json()
        assert res["success"]
        return res["length"]

    def get_keys(self, session_id: SessionId) -> list[str]:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        resp = retry_on_disconnect(lambda: self._api.post(
            self._url("/keys"), json=obj, headers=self._headers()))
        res: WorkerKeysResponse = resp.json()
        return res["keys"]

    def notify_signal(self, session_id: SessionId, key: str) -> None:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        obj["key"] = key
        resp = retry_on_disconnect(lambda: self._api.post(
            self._url("/signal"), json=obj, headers=self._headers()))
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
            # NOTE: don't retry
            # FIXME: think of a better retry strategy here
            resp = self._api.post(
                self._url("/signal"), json=obj, headers=self._headers())
            resp.raise_for_status()
            res: WorkerSignalResponse = resp.json()
            assert "signal" in res

    def remove(self, session_id: SessionId) -> None:
        # NOTE: handled by RemoteSessionUser
        pass
