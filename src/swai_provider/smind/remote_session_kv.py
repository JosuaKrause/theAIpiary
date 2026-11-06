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
import time
from collections.abc import Callable
from typing import TypeVar

import requests
from scattermind.system.base import L_REMOTE, Locality, SessionId
from scattermind.system.names import UName
from scattermind.system.session.session import SessionKeyValue
from scattermind.system.util import get_time_str

from swai.auth import get_authorization
from swai.server_response_types import (
    WorkerKeysResponse,
    WorkerSignalResponse,
    WorkerValueResponse,
)
from swai.system.base import (
    long_poll_timeout,
    REQUEST_TIMEOUT,
    retry_on_disconnect,
)
from swai.system.user import WorkerToken
from swai_provider.env import envload_str


T = TypeVar('T')


SIGNAL_RETRY_WAIT = 0.5  # 0.5s
"""Initial wait before repeating a failed wait for a signal."""
SIGNAL_RETRY_WAIT_MAX = 8.0  # 8s
"""Maximum wait before repeating a failed wait for a signal."""


class SignalWaitFailed(Exception):
    """The server could not be reached while waiting for a signal."""


class RemoteSessionKeyValue(SessionKeyValue):
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
            self._url("/value"), json=obj, headers=self._headers(),
            timeout=REQUEST_TIMEOUT))
        res: WorkerValueResponse = resp.json()
        assert res["success"]

    def push_value(self, session_id: SessionId, key: str, value: str) -> None:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        obj["op"] = "push"
        obj["key"] = key
        obj["value"] = value
        resp = retry_on_disconnect(lambda: self._api.post(
            self._url("/value"), json=obj, headers=self._headers(),
            timeout=REQUEST_TIMEOUT))
        res: WorkerValueResponse = resp.json()
        assert res["success"]

    def pop_value(self, session_id: SessionId, key: str) -> str | None:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        obj["op"] = "pop"
        obj["key"] = key
        resp = retry_on_disconnect(lambda: self._api.post(
            self._url("/value"), json=obj, headers=self._headers(),
            timeout=REQUEST_TIMEOUT))
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
            self._url("/value"), json=obj, headers=self._headers(),
            timeout=REQUEST_TIMEOUT))
        res: WorkerValueResponse = resp.json()
        assert res["success"]
        return res["value"]

    def get_length(self, session_id: SessionId, key: str) -> int:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        obj["op"] = "length"
        obj["key"] = key
        resp = retry_on_disconnect(lambda: self._api.post(
            self._url("/value"), json=obj, headers=self._headers(),
            timeout=REQUEST_TIMEOUT))
        res: WorkerValueResponse = resp.json()
        assert res["success"]
        return res["length"]

    def get_keys(self, session_id: SessionId) -> list[str]:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        resp = retry_on_disconnect(lambda: self._api.post(
            self._url("/keys"), json=obj, headers=self._headers(),
            timeout=REQUEST_TIMEOUT))
        res: WorkerKeysResponse = resp.json()
        return res["keys"]

    def notify_signal(self, session_id: SessionId, key: str) -> None:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        obj["key"] = key
        resp = retry_on_disconnect(lambda: self._api.post(
            self._url("/signal"), json=obj, headers=self._headers(),
            timeout=REQUEST_TIMEOUT))
        res: WorkerSignalResponse = resp.json()
        assert res["signal"]

    def _wait_request(
            self,
            obj: dict[str, str | int | float | list[str] | None],
            wait: float) -> requests.Response:
        return retry_on_disconnect(
            lambda: self._api.post(
                self._url("/wait"),
                json=obj,
                headers=self._headers(),
                timeout=long_poll_timeout(wait)),
            retries=0,
            unify=SignalWaitFailed)

    def wait_for_signal(
            self,
            session_id: SessionId,
            key: str,
            condition: Callable[[], T],
            *,
            timeout: float) -> T | None:
        start_time = time.monotonic()
        retry_wait = SIGNAL_RETRY_WAIT

        def get_remaining() -> float:
            return timeout - (time.monotonic() - start_time)

        while True:
            value = condition()
            if bool(value):
                return value
            remaining = get_remaining()
            if remaining <= 0.0:
                return None
            obj = self._json()
            obj["session"] = session_id.to_parseable()
            obj["key"] = key
            obj["timeout"] = remaining
            # NOTE: retry_on_disconnect cannot repeat the request as is since
            # the remaining wait shrinks. instead a failed request counts as a
            # missed signal: the condition is checked again and the request is
            # repeated with the remaining wait after a backoff. the overall
            # timeout bounds the retries
            try:
                resp = self._wait_request(obj, remaining)
            except SignalWaitFailed:
                print(
                    f"{get_time_str()} could not wait for signal! "
                    "retrying...")
                time.sleep(max(0.0, min(retry_wait, get_remaining())))
                retry_wait = min(retry_wait * 2.0, SIGNAL_RETRY_WAIT_MAX)
                continue
            retry_wait = SIGNAL_RETRY_WAIT
            res: WorkerSignalResponse = resp.json()
            assert "signal" in res

    def remove(self, session_id: SessionId) -> None:
        # NOTE: handled by RemoteSessionUser
        pass
