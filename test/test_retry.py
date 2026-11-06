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
"""Tests for retrying requests to the server."""
from collections.abc import Callable
from http.client import RemoteDisconnected
from types import SimpleNamespace

import pytest
import requests
from urllib3.connection import HTTPConnection
from urllib3.connectionpool import HTTPConnectionPool
from urllib3.exceptions import (
    ConnectTimeoutError,
    MaxRetryError,
    NewConnectionError,
    ProtocolError,
)

from swai.system import base as base_module
from swai.system.base import is_unsent, retry_on_disconnect


MAX_CALLS = 20
"""Calls after which a callback gives up so a broken retry loop fails the test
instead of hanging it."""


class Unified(Exception):
    """Exception used as `unify` argument."""


def response(status_code: int) -> requests.Response:
    """
    Creates a response with the given status code.

    Args:
        status_code (int): The status code.

    Returns:
        requests.Response: The response.
    """
    resp = requests.Response()
    resp.status_code = status_code
    resp.url = "http://localhost/test"
    return resp


class Calls:  # pylint: disable=too-few-public-methods
    """Callback that plays back a list of results (the last one repeats)."""

    def __init__(
            self,
            results: list[int | BaseException]) -> None:
        self._results = results
        self.count = 0

    def __call__(self) -> requests.Response:
        self.count += 1
        if self.count > MAX_CALLS:
            raise AssertionError(f"called more than {MAX_CALLS} times")
        res = self._results[min(self.count, len(self._results)) - 1]
        if isinstance(res, BaseException):
            raise res
        return response(res)


@pytest.fixture(name="sleeps")
def fixture_sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """
    Records the sleeps of the retry loop instead of sleeping.

    Returns:
        list[float]: The recorded sleep durations.
    """
    sleeps: list[float] = []
    monkeypatch.setattr(
        base_module, "time", SimpleNamespace(sleep=sleeps.append))
    return sleeps


def counter() -> tuple[list[int], Callable[[], None]]:
    """
    Creates an `on_retry` callback that counts its calls.

    Returns:
        tuple[list[int], Callable[[], None]]: The call count (single element
            list) and the callback.
    """
    count = [0]

    def on_retry() -> None:
        count[0] += 1

    return count, on_retry


def test_on_retry_is_called(
        sleeps: list[float], capsys: pytest.CaptureFixture[str]) -> None:
    """The `on_retry` argument replaces the built-in log message."""
    count, on_retry = counter()
    calls = Calls([requests.ConnectionError(), 200])
    resp = retry_on_disconnect(
        calls,
        idempotent=True, retries=3, wait_before_retry=2.0, on_retry=on_retry)
    assert resp.status_code == 200
    assert calls.count == 2
    assert count[0] == 1
    assert sleeps == [2.0]
    assert "could not connect" not in capsys.readouterr().out


def test_default_on_retry_logs(
        sleeps: list[float], capsys: pytest.CaptureFixture[str]) -> None:
    """Without `on_retry` the retry is logged."""
    calls = Calls([requests.ConnectionError(), 200])
    resp = retry_on_disconnect(
            calls,
            idempotent=True,
            retries=3,
            wait_before_retry=2.0)
    assert resp.status_code == 200
    assert sleeps == [2.0]
    assert "could not connect" in capsys.readouterr().out


def test_connection_code_waits_and_retries(sleeps: list[float]) -> None:
    """A gateway timeout waits before retrying, like a connection error."""
    count, on_retry = counter()
    calls = Calls([504, 504, 200])
    resp = retry_on_disconnect(
        calls,
        idempotent=True, retries=3, wait_before_retry=1.5, on_retry=on_retry)
    assert resp.status_code == 200
    assert calls.count == 3
    assert count[0] == 2
    assert sleeps == [1.5, 1.5]


def test_connection_code_respects_retries(sleeps: list[float]) -> None:
    """Gateway timeouts stop after `retries` retries."""
    count, on_retry = counter()
    calls = Calls([504])
    with pytest.raises(requests.HTTPError):
        retry_on_disconnect(
            calls,
            idempotent=True,
            retries=2,
            wait_before_retry=1.0,
            on_retry=on_retry)
    assert calls.count == 3
    assert count[0] == 2
    assert sleeps == [1.0, 1.0]


def test_connection_code_unify(sleeps: list[float]) -> None:
    """Exhausted gateway timeouts are unified like connection errors."""
    calls = Calls([504])
    with pytest.raises(Unified):
        retry_on_disconnect(
            calls,
            idempotent=True, retries=1, wait_before_retry=1.0, unify=Unified)
    assert calls.count == 2
    assert sleeps == [1.0]


def test_connection_code_no_retries(sleeps: list[float]) -> None:
    """With zero retries a gateway timeout fails right away."""
    calls = Calls([504])
    with pytest.raises(requests.HTTPError):
        retry_on_disconnect(
                calls,
                idempotent=True,
                retries=0,
                wait_before_retry=1.0)
    assert calls.count == 1
    assert not sleeps


def test_retry_forever(sleeps: list[float]) -> None:
    """Without `retries` the call is retried until it succeeds."""
    calls = Calls([
        504,
        requests.ConnectionError(),
        requests.ReadTimeout(),
        504,
        requests.ConnectTimeout(),
        504,
        200,
    ])
    resp = retry_on_disconnect(calls, idempotent=True, wait_before_retry=3.0)
    assert resp.status_code == 200
    assert calls.count == 7
    assert sleeps == [3.0] * 6


def test_timeouts_are_retried(sleeps: list[float]) -> None:
    """Read timeouts are retried like connection errors."""
    count, on_retry = counter()
    calls = Calls([requests.ReadTimeout(), 200])
    resp = retry_on_disconnect(
        calls,
        idempotent=True, retries=1, wait_before_retry=1.0, on_retry=on_retry)
    assert resp.status_code == 200
    assert count[0] == 1
    assert sleeps == [1.0]

    calls = Calls([requests.ReadTimeout()])
    with pytest.raises(Unified):
        retry_on_disconnect(
            calls,
            idempotent=True, retries=2, wait_before_retry=1.0, unify=Unified)
    assert calls.count == 3


def test_general_http_errors(sleeps: list[float]) -> None:
    """Other HTTP errors are only retried if requested."""
    calls = Calls([500, 200])
    with pytest.raises(requests.HTTPError):
        retry_on_disconnect(
                calls,
                idempotent=True,
                retries=3,
                wait_before_retry=1.0)
    assert calls.count == 1
    assert not sleeps

    calls = Calls([500, 200])
    resp = retry_on_disconnect(
        calls,
        idempotent=True,
        retries=3,
        wait_before_retry=1.0,
        include_general_http_errors=True)
    assert resp.status_code == 200
    assert calls.count == 2
    assert sleeps == [1.0]


def test_no_wait(sleeps: list[float]) -> None:
    """A wait of zero does not sleep."""
    calls = Calls([504, 200])
    resp = retry_on_disconnect(
            calls,
            idempotent=True,
            retries=1,
            wait_before_retry=0.0)
    assert resp.status_code == 200
    assert not sleeps


def refused() -> requests.ConnectionError:
    """
    The error of a request whose connection was refused, as raised by
    requests.

    Returns:
        requests.ConnectionError: The error.
    """
    conn = HTTPConnection("localhost", 1)
    return requests.ConnectionError(MaxRetryError(
        HTTPConnectionPool("localhost", 1),
        "/test",
        NewConnectionError(conn, "Connection refused")))


def connect_timeout() -> requests.ConnectTimeout:
    """
    The error of a request whose connection timed out, as raised by requests.

    Returns:
        requests.ConnectTimeout: The error.
    """
    conn = HTTPConnection("localhost", 1)
    return requests.ConnectTimeout(MaxRetryError(
        HTTPConnectionPool("localhost", 1),
        "/test",
        ConnectTimeoutError(conn, "timed out")))


def aborted() -> requests.ConnectionError:
    """
    The error of a request whose connection broke after it was sent, as
    raised by requests.

    Returns:
        requests.ConnectionError: The error.
    """
    return requests.ConnectionError(ProtocolError(
        "Connection aborted.",
        RemoteDisconnected("Remote end closed connection without response")))


def test_is_unsent() -> None:
    """Only errors before the connection was established are unsent."""
    assert is_unsent(refused())
    assert is_unsent(connect_timeout())
    assert is_unsent(requests.ConnectTimeout())
    assert is_unsent(ConnectionRefusedError())
    assert not is_unsent(aborted())
    assert not is_unsent(requests.ReadTimeout())
    assert not is_unsent(requests.ConnectionError())
    assert not is_unsent(requests.HTTPError())
    assert not is_unsent(ValueError())


@pytest.mark.parametrize("error", [
    requests.ReadTimeout(),
    aborted(),
    requests.ConnectionError(),
])
def test_non_idempotent_sent_is_not_retried(
        sleeps: list[float], error: BaseException) -> None:
    """A non-idempotent request that might have reached the server is not
    retried; the error is raised as is (not unified)."""
    count, on_retry = counter()
    calls = Calls([error, 200])
    with pytest.raises(type(error)) as exc_info:
        retry_on_disconnect(
            calls,
            retries=3,
            wait_before_retry=1.0,
            unify=Unified,
            on_retry=on_retry)
    assert exc_info.value is error
    assert calls.count == 1
    assert count[0] == 0
    assert not sleeps


def test_non_idempotent_connection_code_is_not_retried(
        sleeps: list[float]) -> None:
    """A gateway timeout means the request got to the gateway; a
    non-idempotent request is not repeated."""
    calls = Calls([504, 200])
    with pytest.raises(requests.HTTPError):
        retry_on_disconnect(calls, retries=3, wait_before_retry=1.0)
    assert calls.count == 1
    assert not sleeps


@pytest.mark.parametrize("make_error", [
    connect_timeout,
    requests.ConnectTimeout,
    refused,
    ConnectionRefusedError,
])
def test_non_idempotent_unsent_is_retried(
        sleeps: list[float],
        make_error: Callable[[], BaseException]) -> None:
    """A request that was certainly not sent is retried even if it is not
    idempotent."""
    count, on_retry = counter()
    calls = Calls([make_error(), make_error(), 200])
    resp = retry_on_disconnect(
        calls, retries=3, wait_before_retry=1.0, on_retry=on_retry)
    assert resp.status_code == 200
    assert calls.count == 3
    assert count[0] == 2
    assert sleeps == [1.0, 1.0]

    calls = Calls([make_error()])
    with pytest.raises(Unified):
        retry_on_disconnect(
            calls, retries=1, wait_before_retry=1.0, unify=Unified)
    assert calls.count == 2


def test_general_http_errors_require_idempotent() -> None:
    """Retrying general HTTP errors of a non-idempotent request is refused
    up front."""
    calls = Calls([200])
    with pytest.raises(ValueError, match="idempotent"):
        retry_on_disconnect(calls, include_general_http_errors=True)
    assert calls.count == 0
