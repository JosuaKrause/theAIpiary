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
"""Tests for reading integer settings from the environment."""
import pytest

from swai_provider.env import envload_int as provider_envload_int
from swai_server.env import envload_int


@pytest.mark.parametrize("load", [envload_int, provider_envload_int])
def test_envload_int(
        monkeypatch: pytest.MonkeyPatch,
        load: object) -> None:
    assert callable(load)
    monkeypatch.setenv("REDIS_PORT", "6380")
    assert load("REDIS_PORT", default=6379) == 6380
    monkeypatch.setenv("REDIS_PORT", " ")
    assert load("REDIS_PORT", default=6379) == 6379
    monkeypatch.setenv("REDIS_PORT", "")
    assert load("REDIS_PORT", default=6379) == 6379
    with pytest.raises(ValueError, match="must be set"):
        load("REDIS_PORT")
    monkeypatch.delenv("REDIS_PORT")
    assert load("REDIS_PORT", default=6379) == 6379
    with pytest.raises(ValueError, match="must be set"):
        load("REDIS_PORT")
