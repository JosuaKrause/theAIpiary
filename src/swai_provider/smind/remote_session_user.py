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
from swai.system.user.manager import WorkerToken
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
