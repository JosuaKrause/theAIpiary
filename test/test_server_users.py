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
"""Tests for the unauthenticated password reset endpoints of the API server,
run against the real request handlers on in-memory stores."""
import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass, field
from test.util import ADMIN_EMAIL, memory_redis
from typing import Any, cast

import pytest
from quick_server import create_server
from scattermind.system.names import UName

from swai_server import config as config_module
from swai_server.app import server as server_module
from swai_server.auction import queue as queue_module
from swai_server.system.user import redis as user_redis_module
from swai_server.system.user.loader import load_user_manager
from swai_server.system.user.manager import ResetToken, UserInfo, UserManager


ALICE = UName("alice@example.com")
NOBODY = UName("nobody@example.com")
SOME_TIME = 5.0


@dataclass
class Api:
    """A running API server and what it did behind the scenes."""
    url: str
    user_mng: UserManager
    sent: list[tuple[UName, ResetToken]] = field(default_factory=list)
    email_sent: threading.Event = field(default_factory=threading.Event)
    smtp_release: threading.Event = field(default_factory=threading.Event)

    def post(self, path: str, body: dict[str, Any]) -> tuple[int, Any]:
        """
        Sends a JSON POST request to the API.

        Args:
            path (str): The path below the API prefix.
            body (dict[str, Any]): The JSON body.

        Returns:
            tuple[int, Any]: The status code and the parsed JSON response.
        """
        req = urllib.request.Request(
            f"{self.url}{path}",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=SOME_TIME) as res:
                return res.status, json.loads(res.read())
        except urllib.error.HTTPError as err:
            return err.code, err.read().decode("utf-8")


@pytest.fixture(name="api")
def fixture_api(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Any,
        admin_pw_hash: str) -> Iterator[Api]:
    """
    The API server on in-memory redis stores, with email sending replaced by
    a recorder. The recorder only returns once `smtp_release` is set, the
    way a slow SMTP server would.

    Yields:
        Api: The running server.
    """
    monkeypatch.setattr(user_redis_module, "Redis", memory_redis)
    monkeypatch.setattr(queue_module, "Redis", memory_redis)
    monkeypatch.setattr(
        server_module, "get_config", config_module.config_template)
    # NOTE: the session store is only used by the chat and worker endpoints
    monkeypatch.setattr(server_module, "create_session_store", lambda _: None)
    monkeypatch.setattr(
        server_module, "setup_public_files", lambda *_a, **_kw: None)
    monkeypatch.setenv("ADMIN_EMAIL", ADMIN_EMAIL.get())
    monkeypatch.setenv("ADMIN_PW", admin_pw_hash)
    monkeypatch.setenv("UI_PATH", f"{tmp_path}")
    for env in ("SMTP_HOST", "SMTP_USER", "SMTP_PW", "OWN_EMAIL"):
        monkeypatch.delenv(env, raising=False)

    managers: list[UserManager] = []

    def load_and_keep(*args: Any, **kwargs: Any) -> UserManager:
        user_mng = load_user_manager(*args, **kwargs)
        managers.append(user_mng)
        return user_mng

    monkeypatch.setattr(server_module, "load_user_manager", load_and_keep)

    server = create_server(
        ("127.0.0.1", 0),
        parallel=True,
        thread_factory=threading.Thread,
        token_handler=None,
        worker_constructor=None,
        soft_worker_death=True)
    try:
        _, prefix = server_module.setup(
            server,
            deploy=True,
            versions=cast(server_module.VersionDict, {
                "python_version_detail": "",
                "python_version": "",
                "server_version": "AIpiaryServer/test",
                "app_version": "",
                "commit": "",
                "deploy_time": "",
                "start_time": "",
            }))
        server.timeout = 0.05
        port = server.server_address[1]
        api = Api(url=f"http://127.0.0.1:{port}{prefix}", user_mng=managers[0])

        def send_password_reset(
                _config: Any,
                *,
                user: UserInfo,
                reset_token: ResetToken) -> None:
            assert api.smtp_release.wait(SOME_TIME)
            api.sent.append((user["email"], reset_token))
            api.email_sent.set()

        monkeypatch.setattr(
            server_module, "send_password_reset", send_password_reset)

        def serve() -> None:
            while not server.done:
                server.handle_request()

        serve_thread = threading.Thread(target=serve, daemon=True)
        serve_thread.start()
        yield api
        api.smtp_release.set()
        server.done = True
        serve_thread.join(SOME_TIME)
    finally:
        server.server_close()


def request_reset(api: Api, email: UName) -> tuple[int, Any]:
    """
    Asks the API for a password reset email.

    Args:
        api (Api): The server.
        email (UName): The email entered on the reset password page.

    Returns:
        tuple[int, Any]: The status code and the response.
    """
    return api.post("/user/reset_password_token", {"name": email.get()})


def test_reset_password_email(api: Api) -> None:
    """A reset request for an account sends the email with a token that
    sets the password."""
    assert api.user_mng.create_user(ALICE, "Alice")
    api.smtp_release.set()
    assert request_reset(api, ALICE) == (200, {"email": ALICE.get()})
    assert api.email_sent.wait(SOME_TIME)
    assert len(api.sent) == 1
    email, reset_token = api.sent[0]
    assert email == ALICE
    status, res = api.post(
        "/user/reset_password",
        {"reset_token": reset_token, "password": "alice pw"})
    assert status == 200
    assert res["logged"]
    assert res["email"] == ALICE.get()
    assert api.user_mng.login(ALICE, "alice pw") is not None


def test_reset_password_does_not_reveal_accounts(api: Api) -> None:
    """The reset request cannot be used to probe which accounts exist: the
    answer is the same for an account, an unknown email, an account in its
    cooldown and the admin, and it does not wait for the email to be sent."""
    assert api.user_mng.create_user(ALICE, "Alice")
    # sending the email blocks until released; answering must not wait
    alice = request_reset(api, ALICE)
    assert not api.email_sent.is_set()
    nobody = request_reset(api, NOBODY)
    cooldown = request_reset(api, ALICE)
    admin = request_reset(api, ADMIN_EMAIL)
    assert alice == (200, {"email": ALICE.get()})
    assert nobody == (200, {"email": NOBODY.get()})
    assert cooldown == alice
    assert admin == (200, {"email": ADMIN_EMAIL.get()})
    api.smtp_release.set()
    assert api.email_sent.wait(SOME_TIME)
    # only the first request for the existing account sends an email
    assert [email for email, _ in api.sent] == [ALICE]


def test_reset_password_with_unknown_token(api: Api) -> None:
    status, res = api.post(
        "/user/reset_password",
        {"reset_token": "0" * 32, "password": "pw"})
    assert status == 200
    assert not res["logged"]
