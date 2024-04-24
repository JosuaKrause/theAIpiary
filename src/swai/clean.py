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
