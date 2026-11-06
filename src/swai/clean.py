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
import re
import unicodedata
from html import unescape
from typing import overload


def clean(text: str) -> str:
    text = text.strip()
    while True:
        prev_text = text
        text = unescape(text)
        if prev_text == text:
            break
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"\n\n+", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\n\n+", "\n\n", text)
    text = re.sub(r"\s\s+", " ", text)  # ignore all newlines...
    return text


def strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?\s*>", "\n", text.strip())
    text = re.sub(r"<(?:\"[^\"]*\"['\"]*|'[^']*'['\"]*|[^'\">])+>", "", text)
    return text


@overload
def normalize_text(text: str) -> str:
    ...


@overload
def normalize_text(text: None) -> None:
    ...


def normalize_text(text: str | None) -> str | None:
    if text is None:
        return None
    return clean(strip_html(text)).strip()


BOP = "{"
BCL = "}"
RED_FLAGS: list[str] = ["null", "none", "undefined", "void", "0"]
RED_FLAG_VARIATIONS: set[str] = {
    rtext
    for red in RED_FLAGS
    for rtext in (red, f"({red})", f"{BOP}{red}{BCL}")
}
RED_LEN = max((len(red) for red in RED_FLAG_VARIATIONS))


@overload
def sanity_check(text: str) -> str:
    ...


@overload
def sanity_check(text: None) -> None:
    ...


def sanity_check(text: str | None) -> str | None:
    if text is None:
        return None
    text = f"{text}"
    canonical = text.strip()
    if len(canonical) > RED_LEN:
        return text
    canonical = canonical.lower()
    if canonical in RED_FLAG_VARIATIONS:
        raise ValueError(
            f"{canonical=} in {text=}! this might be a bug on the sender side")
    return text


SHORT_PAT = re.compile(r".\b")
SHORT_LENGTH = 60
SHORT_HARD_LENGTH = 80


def shorten(text: str) -> str:
    text = text.strip()
    if len(text) < SHORT_LENGTH:
        return text
    match = SHORT_PAT.search(text, SHORT_LENGTH, SHORT_HARD_LENGTH)
    if match is None:
        return text[:SHORT_HARD_LENGTH].strip()
    return text[:match.end() + 1].strip()
