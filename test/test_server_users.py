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
"""Tests for the user endpoints of the API server, run against the real
request handlers on in-memory stores, once with each user manager."""
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
from scattermind.system.names import GNamespace, UName
from scattermind.system.response import response_to_redis
from scattermind.system.session.session import SessionStore

from swai.auth import get_authorization
from swai.system.user import (
    CAP_CHANGE_CAPABILITIES,
    CAP_CHANGE_EMAIL,
    CAP_CREATE_USER,
    CAP_DELETE_USER,
    CAP_LIST_USERS,
    CAP_LOGOUT_OTHER_USER,
    CAP_REGISTER_OWN_WORKER,
    CAPABILITIES,
    CapabilityName,
)
from swai_server import config as config_module
from swai_server.app import server as server_module
from swai_server.auction import queue as queue_module
from swai_server.auction.queue import TaskQueue
from swai_server.system.user.manager import (
    ResetToken,
    SessionToken,
    UserInfo,
    UserManager,
)


ALICE = UName("alice@example.com")
BOB = UName("bob@example.com")
NOBODY = UName("nobody@example.com")
SOME_TIME = 5.0


@dataclass
class Api:
    """A running API server and what it did behind the scenes."""
    url: str
    user_mng: UserManager
    session_store: SessionStore
    task_queue: TaskQueue
    sent: list[tuple[UName, ResetToken]] = field(default_factory=list)
    email_sent: threading.Event = field(default_factory=threading.Event)
    smtp_release: threading.Event = field(default_factory=threading.Event)

    def post(
            self,
            path: str,
            body: dict[str, Any],
            *,
            session: SessionToken | None = None,
            method: str = "POST",
            headers: dict[str, str] | None = None) -> tuple[int, Any]:
        """
        Sends a JSON request to the API.

        Args:
            path (str): The path below the API prefix.
            body (dict[str, Any]): The JSON body.
            session (SessionToken | None, optional): The session cookie to
                send. Defaults to None.
            method (str, optional): The HTTP method. Defaults to "POST".
            headers (dict[str, str] | None, optional): Additional headers.
                Defaults to None.

        Returns:
            tuple[int, Any]: The status code and the parsed JSON response.
        """
        all_headers = {"Content-Type": "application/json"}
        if session is not None:
            all_headers["Cookie"] = f"user_session={session}"
        if headers is not None:
            all_headers.update(headers)
        req = urllib.request.Request(
            f"{self.url}{path}",
            data=json.dumps(body).encode("utf-8"),
            headers=all_headers,
            method=method)
        try:
            with urllib.request.urlopen(req, timeout=SOME_TIME) as res:
                return res.status, json.loads(res.read())
        except urllib.error.HTTPError as err:
            return err.code, err.read().decode("utf-8")


@pytest.fixture(name="api")
def fixture_api(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Any,
        admin_pw_hash: str,
        user_mng: UserManager,
        session_store: SessionStore) -> Iterator[Api]:
    """
    The API server on in-memory stores (and the user manager under test),
    with email sending replaced by a recorder. The recorder only returns
    once `smtp_release` is set, the way a slow SMTP server would.

    Yields:
        Api: The running server.
    """
    monkeypatch.setattr(queue_module, "Redis", memory_redis)
    task_queues: list[TaskQueue] = []

    def create_task_queue(*args: Any, **kwargs: Any) -> TaskQueue:
        task_queue = TaskQueue(*args, **kwargs)
        task_queues.append(task_queue)
        return task_queue

    monkeypatch.setattr(server_module, "TaskQueue", create_task_queue)
    monkeypatch.setattr(
        server_module, "get_config", config_module.config_template)
    monkeypatch.setattr(
        server_module, "create_session_store", lambda _: session_store)
    monkeypatch.setattr(
        server_module, "setup_public_files", lambda *_a, **_kw: None)
    monkeypatch.setenv("ADMIN_EMAIL", ADMIN_EMAIL.get())
    monkeypatch.setenv("ADMIN_PW", admin_pw_hash)
    monkeypatch.setenv("UI_PATH", f"{tmp_path}")
    for env in ("SMTP_HOST", "SMTP_USER", "SMTP_PW", "OWN_EMAIL"):
        monkeypatch.delenv(env, raising=False)

    # NOTE: the user manager fixture has the same admin as the environment
    monkeypatch.setattr(
        server_module, "load_user_manager", lambda *_a, **_kw: user_mng)

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
        api = Api(
            url=f"http://127.0.0.1:{port}{prefix}",
            user_mng=user_mng,
            session_store=session_store,
            task_queue=task_queues[0])

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


# *** admin endpoints ***


def session_for(
        api: Api, email: UName, *capabilities: CapabilityName) -> SessionToken:
    """
    Creates the account (unless it is the admin), grants it the given
    capabilities, and starts a session for it.

    Args:
        api (Api): The server.
        email (UName): The account.
        *capabilities (CapabilityName): The capabilities to grant.

    Returns:
        SessionToken: A session of the account.
    """
    user_mng = api.user_mng
    if email != ADMIN_EMAIL:
        assert user_mng.create_user(email, f"display {email.get()}")
    for cap in capabilities:
        user_mng.set_capability(email, cap, has=True)
    token = user_mng.do_login(email)
    assert token is not None
    return token


def is_logged_in(api: Api, session: SessionToken) -> bool:
    """
    Asks the server whether a session is logged in.

    Args:
        api (Api): The server.
        session (SessionToken): The session.

    Returns:
        bool: Whether the session is logged in.
    """
    status, res = api.post("/user/current", {}, session=session)
    assert status == 200
    return res["logged"]


def test_admin_endpoints_need_login(api: Api) -> None:
    session_for(api, BOB)
    requests: list[tuple[str, str, dict[str, Any]]] = [
        ("/user/send_reset", "POST", {"name": BOB.get()}),
        ("/user/delete", "POST", {"name": BOB.get()}),
        ("/user/logout", "POST", {"name": BOB.get()}),
        ("/user/list", "POST", {}),
        (
            "/user/capability",
            "PUT",
            {
                "name": BOB.get(),
                "capability": CAP_CREATE_USER,
                "set_has": True,
            },
        ),
    ]
    for path, method, body in requests:
        status, _ = api.post(path, body, method=method)
        assert status == 401, path
        status, _ = api.post(
            path, body, method=method, session="not a session")
        assert status == 401, path
    assert BOB in set(api.user_mng.list_users())


def test_send_reset_endpoint(api: Api) -> None:
    alice = session_for(api, ALICE)
    session_for(api, BOB)
    api.smtp_release.set()
    # sending a reset to someone else needs the capability to create users
    status, _ = api.post(
        "/user/send_reset", {"name": BOB.get()}, session=alice)
    assert status == 403
    assert not api.sent
    admin = session_for(api, ADMIN_EMAIL)
    assert api.post(
        "/user/send_reset", {"name": BOB.get()}, session=admin,
    ) == (200, {"email": BOB.get(), "sent": True})
    assert api.sent[-1][0] == BOB
    reset_token = api.sent[-1][1]
    # the admin learns about the cooldown, unknown accounts, and the admin
    for email in (BOB, NOBODY, ADMIN_EMAIL):
        assert api.post(
            "/user/send_reset", {"name": email.get()}, session=admin,
        ) == (200, {"email": email.get(), "sent": False})
    assert [email for email, _ in api.sent] == [BOB]
    status, res = api.post(
        "/user/reset_password",
        {"reset_token": reset_token, "password": "bob pw"})
    assert status == 200
    assert res["logged"]
    assert api.user_mng.login(BOB, "bob pw") is not None
    # with the capability (a user that is not the admin)
    api.user_mng.set_capability(ALICE, CAP_CREATE_USER, has=True)
    assert api.post(
        "/user/send_reset", {"name": BOB.get()}, session=alice,
    ) == (200, {"email": BOB.get(), "sent": True})


def test_logout_other_user_endpoint(api: Api) -> None:
    alice = session_for(api, ALICE)
    bob = session_for(api, BOB)
    bob_other = api.user_mng.do_login(BOB)
    assert bob_other is not None
    status, _ = api.post("/user/logout", {"name": BOB.get()}, session=alice)
    assert status == 403
    assert is_logged_in(api, bob)
    admin = session_for(api, ADMIN_EMAIL)
    status, res = api.post(
        "/user/logout", {"name": BOB.get()}, session=admin)
    assert status == 200
    assert not res["logged"]
    assert not is_logged_in(api, bob)
    assert not is_logged_in(api, bob_other)
    # the admin stays logged in, and so does everybody else
    assert is_logged_in(api, admin)
    assert is_logged_in(api, alice)
    # with the capability (a user that is not the admin)
    bob_again = api.user_mng.do_login(BOB)
    assert bob_again is not None
    api.user_mng.set_capability(ALICE, CAP_LOGOUT_OTHER_USER, has=True)
    status, _ = api.post("/user/logout", {"name": BOB.get()}, session=alice)
    assert status == 200
    assert not is_logged_in(api, bob_again)


def test_delete_user_endpoint(api: Api) -> None:
    """Deleting an account ends its sessions, disconnects its workers, and
    removes its chats; other accounts keep theirs."""
    user_mng = api.user_mng
    session_store = api.session_store
    alice = session_for(api, ALICE, CAP_REGISTER_OWN_WORKER)
    bob = session_for(api, BOB)
    worker_token = user_mng.create_worker_token(ALICE)
    assert worker_token is not None
    worker_auth = {"Authorization": get_authorization(ALICE, worker_token)}
    heartbeat = {"worker_name": "hive", "status": "idle"}
    assert api.post(
        "/task/heartbeat", heartbeat, headers=worker_auth)[0] == 200
    alice_id = user_mng.get_user_id(ALICE)
    bob_id = user_mng.get_user_id(BOB)
    assert alice_id is not None
    assert bob_id is not None
    alice_chats = [
        session_store.create_new_session(
            alice_id, copy_from=None).get_session_id()
        for _ in range(2)
    ]
    bob_chat = session_store.create_new_session(
        bob_id, copy_from=None).get_session_id()

    # without the capability
    status, _ = api.post("/user/delete", {"name": ALICE.get()}, session=bob)
    assert status == 403
    assert is_logged_in(api, alice)

    admin = session_for(api, ADMIN_EMAIL)
    assert api.post(
        "/user/delete", {"name": ALICE.get()}, session=admin,
    ) == (200, {"email": ALICE.get(), "deleted": True, "chats": 2})
    assert ALICE not in set(user_mng.list_users())
    assert not is_logged_in(api, alice)
    assert api.post(
        "/task/heartbeat", heartbeat, headers=worker_auth)[0] == 401
    assert user_mng.get_user_id(ALICE) is None
    assert not list(session_store.get_sessions(alice_id))
    for chat in alice_chats:
        assert session_store.get_user(chat) is None
    assert session_store.get_user(bob_chat) == bob_id
    assert is_logged_in(api, bob)
    # again: nothing left to delete
    assert api.post(
        "/user/delete", {"name": ALICE.get()}, session=admin,
    ) == (200, {"email": ALICE.get(), "deleted": False, "chats": 0})


def test_delete_user_endpoint_spares_self_and_admin(api: Api) -> None:
    alice = session_for(api, ALICE, CAP_DELETE_USER)
    admin = session_for(api, ADMIN_EMAIL)
    for who, email in [
            (alice, ALICE),
            (alice, ADMIN_EMAIL),
            (admin, ADMIN_EMAIL),
            ]:
        status, _ = api.post(
            "/user/delete", {"name": email.get()}, session=who)
        assert status == 403
    assert is_logged_in(api, alice)
    assert is_logged_in(api, admin)
    session_for(api, BOB)
    # with the capability (a user that is not the admin)
    assert api.post(
        "/user/delete", {"name": BOB.get()}, session=alice,
    ) == (200, {"email": BOB.get(), "deleted": True, "chats": 0})


def change_capability(
        api: Api,
        session: SessionToken,
        email: UName,
        capability: CapabilityName,
        set_has: bool) -> tuple[int, Any]:
    """
    Changes a capability through the API.

    Args:
        api (Api): The server.
        session (SessionToken): The session of the acting user.
        email (UName): The account to change.
        capability (CapabilityName): The capability.
        set_has (bool): Whether to grant or to revoke it.

    Returns:
        tuple[int, Any]: The status code and the response.
    """
    return api.post(
        "/user/capability",
        {"name": email.get(), "capability": capability, "set_has": set_has},
        session=session,
        method="PUT")


def test_capability_endpoint(api: Api) -> None:
    alice = session_for(api, ALICE)
    session_for(api, BOB)
    assert change_capability(api, alice, BOB, CAP_CREATE_USER, True)[0] == 403
    assert not api.user_mng.list_capabilities(BOB)
    admin = session_for(api, ADMIN_EMAIL)
    assert change_capability(api, admin, BOB, CAP_CREATE_USER, True) == (
        200, {"okay": True, "capabilities": [CAP_CREATE_USER]})
    assert change_capability(api, admin, BOB, CAP_LIST_USERS, True) == (
        200, {"okay": True, "capabilities": [CAP_CREATE_USER, CAP_LIST_USERS]})
    assert change_capability(api, admin, BOB, CAP_CREATE_USER, False) == (
        200, {"okay": True, "capabilities": [CAP_LIST_USERS]})
    assert api.user_mng.list_capabilities(BOB) == {CAP_LIST_USERS}
    # with the capability (a user that is not the admin)
    api.user_mng.set_capability(ALICE, CAP_CHANGE_CAPABILITIES, has=True)
    assert change_capability(api, alice, BOB, CAP_LIST_USERS, False) == (
        200, {"okay": True, "capabilities": []})


def test_admin_capabilities_cannot_change_endpoint(api: Api) -> None:
    admin = session_for(api, ADMIN_EMAIL)
    alice = session_for(api, ALICE, CAP_CHANGE_CAPABILITIES)
    for who in (admin, alice):
        status, _ = change_capability(
            api, who, ADMIN_EMAIL, CAP_CHANGE_CAPABILITIES, False)
        assert status == 403
    assert api.user_mng.list_capabilities(ADMIN_EMAIL) == set(CAPABILITIES)


def test_user_list_marks_admin(api: Api) -> None:
    alice = session_for(api, ALICE)
    status, _ = api.post("/user/list", {}, session=alice)
    assert status == 403
    admin = session_for(api, ADMIN_EMAIL)
    status, res = api.post("/user/list", {}, session=admin)
    assert status == 200
    assert res == {
        "users": [
            {
                "email": ADMIN_EMAIL.get(),
                "display_name": "admin",
                "capabilities": sorted(CAPABILITIES),
                "admin": True,
            },
            {
                "email": ALICE.get(),
                "display_name": f"display {ALICE.get()}",
                "capabilities": [],
                "admin": False,
            },
        ],
    }


# *** changing the email ***


CAROL = UName("carol@example.com")


def change_email(
        api: Api,
        session: SessionToken,
        email: UName,
        new_email: UName) -> tuple[int, Any]:
    """
    Changes the email of an account through the API.

    Args:
        api (Api): The server.
        session (SessionToken): The session of the acting user.
        email (UName): The current email.
        new_email (UName): The new email.

    Returns:
        tuple[int, Any]: The status code and the response.
    """
    return api.post(
        "/user/change_email",
        {"name": email.get(), "new_email": new_email.get()},
        session=session)


def login(api: Api, email: UName, password: str) -> SessionToken | None:
    """
    Logs in through the API.

    Args:
        api (Api): The server.
        email (UName): The email.
        password (str): The password.

    Returns:
        SessionToken | None: The session from the cookie or None if the login
            failed.
    """
    req = urllib.request.Request(
        f"{api.url}/user/login",
        data=json.dumps({"name": email.get(), "password": password}).encode(
            "utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=SOME_TIME) as res:
        if not json.loads(res.read())["logged"]:
            return None
        cookie = res.headers["Set-Cookie"]
    return cookie.split("user_session=", 1)[1].split(";", 1)[0]


def test_change_email_endpoint_permissions(api: Api) -> None:
    alice = session_for(api, ALICE)
    bob = session_for(api, BOB)
    assert api.post(
        "/user/change_email",
        {"name": BOB.get(), "new_email": CAROL.get()})[0] == 401
    assert change_email(api, alice, BOB, CAROL)[0] == 403
    api.user_mng.set_capability(ALICE, CAP_CHANGE_EMAIL, has=True)
    admin = session_for(api, ADMIN_EMAIL)
    # not the own email, not the admin's
    for who, email in [
            (alice, ALICE),
            (alice, ADMIN_EMAIL),
            (admin, ADMIN_EMAIL),
            ]:
        assert change_email(api, who, email, CAROL)[0] == 403
    assert is_logged_in(api, bob)
    # taken emails, including the admin's, and an empty one
    for taken in (ALICE, ADMIN_EMAIL):
        assert change_email(api, admin, BOB, taken) == (200, {
            "email": BOB.get(),
            "new_email": taken.get(),
            "changed": False,
        })
    assert api.post(
        "/user/change_email",
        {"name": BOB.get(), "new_email": " "},
        session=admin)[0] == 400
    assert is_logged_in(api, bob)
    assert set(api.user_mng.list_users()) == {ADMIN_EMAIL, ALICE, BOB}
    # with the capability (a user that is not the admin)
    assert change_email(api, alice, BOB, CAROL) == (200, {
        "email": BOB.get(),
        "new_email": CAROL.get(),
        "changed": True,
    })


def test_change_email_endpoint(api: Api) -> None:
    """After an email change the account logs in with the new email only,
    and keeps its chats, its worker token, its queue workers, and a task its
    worker took before the change."""
    user_mng = api.user_mng
    task_queue = api.task_queue
    session_for(api, BOB, CAP_REGISTER_OWN_WORKER)
    reset_token = user_mng.generate_reset_token(BOB)
    assert reset_token is not None
    assert user_mng.set_password("bob pw", reset_token) == BOB
    bob = login(api, BOB, "bob pw")
    assert bob is not None
    status, res = api.post("/chat/new", {}, session=bob)
    assert status == 200
    chat = res["model_session"]
    worker_token = user_mng.create_worker_token(BOB)
    assert worker_token is not None

    def worker_post(
            email: UName, path: str, body: dict[str, Any]) -> tuple[int, Any]:
        return api.post(path, body, headers={
            "Authorization": get_authorization(email, worker_token),
        })

    heartbeat = {"worker_name": "hive", "status": "idle"}
    assert worker_post(BOB, "/task/heartbeat", heartbeat)[0] == 200
    workers = [info["worker_id"] for info in task_queue.get_all_workers()]
    assert len(workers) == 1
    # a task taken before the change
    task_id = task_queue.enqueue_task(GNamespace("llama"), {"prompt": "hi"})
    status, res = worker_post(BOB, "/task/bid", {
        "worker_name": "hive",
        "nss": ["llama"],
        "timeout": 1.0,
    })
    assert status == 200
    assert res["task_id"] == task_id.to_parseable()

    admin = session_for(api, ADMIN_EMAIL)
    assert change_email(api, admin, BOB, CAROL)[1]["changed"]

    # logged out; only the new email logs in, with the same password
    assert not is_logged_in(api, bob)
    assert login(api, BOB, "bob pw") is None
    carol = login(api, CAROL, "bob pw")
    assert carol is not None
    # the chats stayed
    status, res = api.post("/chat/list", {}, session=carol)
    assert status == 200
    assert [info["model_session"] for info in res["model_sessions"]] == [
        chat]
    # the worker token works with the new email only
    assert worker_post(BOB, "/task/heartbeat", heartbeat)[0] == 401
    assert worker_post(CAROL, "/task/heartbeat", heartbeat)[0] == 200
    # it is the same worker, and still the account's own
    assert [
        info["worker_id"] for info in task_queue.get_all_workers()
    ] == workers
    status, res = api.post("/task/workers", {}, session=carol)
    assert status == 200
    assert [(info["worker_id"], info["own"]) for info in res["workers"]] == [
        (workers[0], True)]
    # the task taken before the change is finished after it
    status, _ = worker_post(CAROL, "/task/finish", {
        "worker_name": "hive",
        "task_id": task_id.to_parseable(),
        "response": response_to_redis({
            "ns": GNamespace("llama"),
            "status": "ready",
            "result": None,
            "duration": 1.0,
            "retries": 0,
            "error": None,
            "fmt": None,
        }),
    })
    assert status == 200
    result = task_queue.get_result(task_id)
    assert result is not None
    assert result["status"] == "ready"
