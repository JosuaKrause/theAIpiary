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
"""Tests for the provider's requests to the server, against a local HTTP
server that answers with scripted (slow, failing) responses."""
import json
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from typing import NamedTuple

import pytest
from scattermind.system.base import SessionId, UserId
from scattermind.system.names import UName

from swai.system import base as base_module
from swai.system.base import WorkerStatus
from swai_provider.app import task_hnd as task_hnd_module
from swai_provider.app.task_hnd import TaskHandler
from swai_provider.app.worker import heartbeat_loop
from swai_provider.smind import remote_session_blob as blob_module
from swai_provider.smind import remote_session_kv as kv_module
from swai_provider.smind.remote_session_blob import RemoteSessionBlob
from swai_provider.smind.remote_session_kv import RemoteSessionKeyValue


SHORT_READ = 0.3
"""The read timeout used in the tests."""
SLOW = 2.0
"""Delay of a response that is too slow for `SHORT_READ`."""


def session_id() -> SessionId:
    """
    Creates a session id.

    Returns:
        SessionId: The session id.
    """
    return SessionId.create_for(UserId.create(UName("user@example.com")))


class Reply(NamedTuple):
    """A scripted reply of the test server."""
    status: int
    body: bytes
    delay: float = 0.0


def ok(obj: object, delay: float = 0.0) -> Reply:
    """
    A successful JSON reply.

    Args:
        obj (object): The JSON object.
        delay (float, optional): The delay of the reply. Defaults to 0.0.

    Returns:
        Reply: The reply.
    """
    return Reply(200, json.dumps(obj).encode("utf-8"), delay)


class Received(NamedTuple):
    """A request received by the test server."""
    method: str
    path: str
    body: bytes


class FakeServer:
    """Local HTTP server that plays back scripted replies per path (the last
    reply of a path repeats)."""

    def __init__(self) -> None:
        self.received: list[Received] = []
        self.replies: dict[str, list[Reply]] = {}
        self._counts: dict[str, int] = {}
        self._lock = threading.Lock()
        self._release = threading.Event()
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def _handle(self) -> None:
                length = int(self.headers.get("content-length", 0))
                body = self.rfile.read(length)
                reply = fake.receive(self.command, self.path, body)
                try:
                    self.send_response(reply.status)
                    self.send_header("content-type", "application/json")
                    self.send_header("content-length", f"{len(reply.body)}")
                    self.end_headers()
                    self.wfile.write(reply.body)
                except OSError:
                    pass  # NOTE: the client gave up already

            do_POST = _handle  # noqa: N815
            do_PUT = _handle  # noqa: N815
            do_DELETE = _handle  # noqa: N815

            def log_message(self, *args: object) -> None:
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            kwargs={"poll_interval": 0.05},
            daemon=True)

    def receive(self, method: str, path: str, body: bytes) -> Reply:
        """
        Records a request and returns its reply after the reply's delay.

        Args:
            method (str): The HTTP method.
            path (str): The path.
            body (bytes): The request body.

        Returns:
            Reply: The reply.
        """
        with self._lock:
            self.received.append(Received(method, path, body))
            count = self._counts.get(path, 0)
            self._counts[path] = count + 1
            replies = self.replies.get(path, [Reply(404, b"")])
            reply = replies[min(count, len(replies) - 1)]
        if reply.delay > 0.0:
            self._release.wait(reply.delay)
        return reply

    def url(self) -> str:
        """
        The base URL of the server.

        Returns:
            str: The URL.
        """
        host, port = self._server.server_address[:2]
        assert isinstance(host, str)
        return f"http://{host}:{port}/"

    def paths(self) -> list[str]:
        """
        The paths of all received requests in order.

        Returns:
            list[str]: The paths.
        """
        with self._lock:
            return [req.path for req in self.received]

    def start(self) -> None:
        """Starts the server."""
        self._thread.start()

    def stop(self) -> None:
        """Stops the server and releases pending slow replies."""
        self._release.set()
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()


@pytest.fixture(name="server")
def fixture_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeServer]:
    """
    A local server with the provider configured to talk to it, short read
    timeouts, and no waiting between retries.

    Yields:
        FakeServer: The server.
    """
    server = FakeServer()
    server.start()
    monkeypatch.setenv("AIPIARY_API_URL", server.url())
    monkeypatch.setenv("AIPIARY_USER", "provider@example.com")
    monkeypatch.setenv("AIPIARY_WORKER_TOKEN", "token")
    timeout = (base_module.CONNECT_TIMEOUT, SHORT_READ)
    monkeypatch.setattr(kv_module, "REQUEST_TIMEOUT", timeout)
    monkeypatch.setattr(blob_module, "REQUEST_TIMEOUT", timeout)
    monkeypatch.setattr(task_hnd_module, "REQUEST_TIMEOUT", timeout)
    monkeypatch.setattr(base_module, "LONG_POLL_GRACE", SHORT_READ)

    def short_sleep(secs: float) -> None:
        time.sleep(min(secs, 0.01))

    # NOTE: only the retry loop's sleep is shortened
    monkeypatch.setattr(
        base_module, "time", SimpleNamespace(sleep=short_sleep))
    try:
        yield server
    finally:
        server.stop()


def test_slow_request_times_out_and_is_retried(server: FakeServer) -> None:
    """A regular request has a read timeout and a timed out request is
    retried."""
    server.replies["/api/smind/value"] = [
        ok({"value": "late", "success": True}, delay=SLOW),
        ok({"value": "fine", "success": True}),
    ]
    kv = RemoteSessionKeyValue()
    start = time.monotonic()
    assert kv.get_value(session_id(), "key", 0) == "fine"
    assert time.monotonic() - start < SLOW
    assert server.paths() == ["/api/smind/value", "/api/smind/value"]


def test_gateway_timeout_is_retried(server: FakeServer) -> None:
    """A gateway timeout is retried."""
    server.replies["/api/smind/value"] = [
        Reply(504, b""),
        Reply(504, b""),
        ok({"value": "fine", "success": True}),
    ]
    kv = RemoteSessionKeyValue()
    assert kv.get_value(session_id(), "key", 0) == "fine"
    assert len(server.paths()) == 3


def test_bid_read_timeout_exceeds_bid_wait(
        server: FakeServer, monkeypatch: pytest.MonkeyPatch) -> None:
    """The bid is a long poll: the server may hold it for the full bid wait
    which is longer than the regular read timeout."""
    monkeypatch.setattr(base_module, "LONG_POLL_GRACE", 1.0)
    wait = SHORT_READ * 2.0
    server.replies["/api/task/bid"] = [
        ok({"ns": None, "task_id": None, "input_data": None}, delay=wait),
    ]
    task_hnd = TaskHandler("worker")
    assert task_hnd.task_bid([], timeout=wait) is None
    assert server.paths() == ["/api/task/bid"]
    received = json.loads(server.received[0].body)
    assert received["timeout"] == wait


def test_bid_times_out_eventually(server: FakeServer) -> None:
    """A bid that the server holds longer than the bid wait is retried."""
    wait = SHORT_READ
    server.replies["/api/task/bid"] = [
        ok({"ns": None, "task_id": None, "input_data": None}, delay=SLOW),
        ok({"ns": None, "task_id": None, "input_data": None}),
    ]
    task_hnd = TaskHandler("worker")
    start = time.monotonic()
    assert task_hnd.task_bid([], timeout=wait) is None
    assert time.monotonic() - start < SLOW
    assert server.paths() == ["/api/task/bid", "/api/task/bid"]


def test_wait_for_signal_waits_on_server(server: FakeServer) -> None:
    """Waiting for a signal long polls the wait endpoint (it must not send a
    signal) and returns None once the timeout has passed."""
    server.replies["/api/smind/wait"] = [ok({"signal": False}, delay=0.1)]
    kv = RemoteSessionKeyValue()
    start = time.monotonic()
    assert kv.wait_for_signal(
        session_id(), "key", lambda: None, timeout=0.25) is None
    assert time.monotonic() - start >= 0.25
    paths = server.paths()
    assert paths
    assert set(paths) == {"/api/smind/wait"}
    received = json.loads(server.received[0].body)
    assert 0.0 < received["timeout"] <= 0.25


def test_wait_for_signal_survives_server_errors(
        server: FakeServer, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed wait is not fatal: the condition is checked again and the
    wait repeated."""
    monkeypatch.setattr(kv_module, "SIGNAL_RETRY_WAIT", 0.01)
    server.replies["/api/smind/wait"] = [
        Reply(504, b""),
        Reply(504, b""),
        ok({"signal": True}),
    ]
    kv = RemoteSessionKeyValue()

    def condition() -> str | None:
        if len(server.paths()) >= 3:
            return "signaled"
        return None

    assert kv.wait_for_signal(
        session_id(), "key", condition, timeout=5.0) == "signaled"
    assert server.paths() == ["/api/smind/wait"] * 3


def test_wait_for_signal_read_timeout(server: FakeServer) -> None:
    """A wait that the server does not answer in time ends shortly after the
    timeout."""
    server.replies["/api/smind/wait"] = [ok({"signal": True}, delay=SLOW)]
    kv = RemoteSessionKeyValue()
    start = time.monotonic()
    assert kv.wait_for_signal(
        session_id(), "key", lambda: None, timeout=0.2) is None
    assert time.monotonic() - start < SLOW
    assert server.paths() == ["/api/smind/wait"]


def test_wait_for_signal_timeout_bounds_retries(server: FakeServer) -> None:
    """If the server stays unreachable the wait ends with the timeout."""
    server.replies["/api/smind/wait"] = [Reply(504, b"")]
    kv = RemoteSessionKeyValue()
    start = time.monotonic()
    assert kv.wait_for_signal(
        session_id(), "key", lambda: None, timeout=0.5) is None
    duration = time.monotonic() - start
    assert 0.5 <= duration < SLOW
    # NOTE: backoff: 0.5s, 1s, ... so only a few attempts fit
    assert 1 <= len(server.paths()) <= 3


def test_blob_upload_retry_resends_chunk(server: FakeServer) -> None:
    """A retried chunk upload sends the full chunk again."""
    server.replies["/api/smind/blob"] = [
        Reply(504, b""),
        ok({"done": True, "missing": []}),
    ]
    blob = RemoteSessionBlob()
    data = b"chunk data that has to arrive"
    with blob.open_blob_write(session_id(), "name") as fout:
        fout.write(data)
    assert len(server.received) == 2
    for req in server.received:
        assert req.method == "PUT"
        assert data in req.body


def test_heartbeat_loop_survives_failures(server: FakeServer) -> None:
    """Failing heartbeats are logged and sent again on the next interval;
    the loop keeps running until shutdown and then reports offline."""
    server.replies["/api/task/heartbeat"] = [
        Reply(200, b"not json"),
        Reply(504, b""),
        Reply(500, b""),
        ok({"timeout": 0.01}, delay=SLOW),
        ok({"timeout": 0.01}),
    ]
    task_hnd = TaskHandler("worker")
    cond = threading.Condition()
    done = threading.Event()
    status_calls = [0]

    def get_status() -> WorkerStatus:
        if done.is_set():
            return "offline"
        status_calls[0] += 1
        if status_calls[0] == 2:
            raise ValueError("status unavailable")
        return "idle"

    th = threading.Thread(
        target=heartbeat_loop,
        args=(task_hnd,),
        kwargs={
            "get_status": get_status,
            "is_done": done.is_set,
            "cond": cond,
            "retry_wait": 0.01,
        },
        daemon=True)
    th.start()
    deadline = time.monotonic() + 10.0
    while len(server.paths()) < 5 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert th.is_alive()
    done.set()
    with cond:
        cond.notify_all()
    th.join(timeout=10.0)
    assert not th.is_alive()
    # NOTE: one get_status call failed before sending a heartbeat
    assert status_calls[0] >= 6
    assert len(server.paths()) >= 6
    last = json.loads(server.received[-1].body)
    assert last["status"] == "offline"
    assert last["worker_name"] == "worker"
