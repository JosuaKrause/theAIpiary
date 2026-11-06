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
from collections.abc import Iterable
from typing import TypeVar

import requests
from scattermind.system.base import L_REMOTE, Locality, SessionId, UserId
from scattermind.system.names import UName
from scattermind.system.session.session import (
    Session,
    SessionStore,
    SessionUser,
)

from swai.auth import get_authorization
from swai.server_response_types import (
    WorkerSessionListResponse,
    WorkerSessionResponse,
    WorkerUserResponse,
)
from swai.system.base import retry_on_disconnect
from swai.system.user import WorkerToken
from swai_provider.env import envload_str


T = TypeVar('T')


class RemoteSessionUser(SessionUser):
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

    def register_session(self, user_id: UserId, session_id: SessionId) -> None:
        obj = self._json()
        obj["user_id"] = user_id.to_parseable()
        obj["session"] = session_id.to_parseable()
        resp = retry_on_disconnect(lambda: self._api.put(
            self._url("/session"), json=obj, headers=self._headers()))
        res: WorkerSessionResponse = resp.json()
        assert res["ok"]

    def get_sessions(
            self,
            sessions: SessionStore,
            user_id: UserId) -> Iterable[Session]:
        obj = self._json()
        obj["user_id"] = user_id.to_parseable()
        resp = retry_on_disconnect(lambda: self._api.post(
            self._url("/session"), json=obj, headers=self._headers()))
        res: WorkerSessionListResponse = resp.json()
        yield from (
            sessions.get_session(SessionId.parse(session))
            for session in res["sessions"]
        )

    def get_user(self, session_id: SessionId) -> UserId | None:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        resp = retry_on_disconnect(lambda: self._api.post(
            self._url("/user"), json=obj, headers=self._headers()))
        res: WorkerUserResponse = resp.json()
        user_id_str = res["user_id"]
        if user_id_str is None:
            return None
        return UserId.parse(user_id_str)

    def remove(self, session_id: SessionId) -> None:
        obj = self._json()
        obj["session"] = session_id.to_parseable()
        resp = retry_on_disconnect(lambda: self._api.delete(
            self._url("/session"), json=obj, headers=self._headers()))
        res: WorkerSessionResponse = resp.json()
        assert res["ok"]
