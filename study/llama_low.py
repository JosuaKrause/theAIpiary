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
import sys
import time
from typing import cast

from llama_cpp import (
    ChatCompletionRequestMessage,
    CreateChatCompletionStreamResponse,
    Llama,
    LlamaDiskCache,
)

from study.util import (
    CONSOLE_COLOR_DEFAULT,
    CONSOLE_COLOR_PROMPT,
    CONSOLE_COLOR_USER_INPUT,
)


CUR_COLOR: str | None = None


def set_color(color: str) -> None:
    global CUR_COLOR  # pylint: disable=global-statement

    if color is None and not sys.stdout.isatty():
        color = "nocolor"
    if color == "nocolor":
        return
    if color == CUR_COLOR:
        return
    print(color, end="")
    sys.stderr.flush()
    sys.stdout.flush()
    CUR_COLOR = color


def run() -> None:
    start_load = time.monotonic()
    model = Llama(
        model_path="./models/Meta-Llama-3-8B-Instruct-IQ3_XS.gguf",
        n_ctx=30000)
    model.set_cache(LlamaDiskCache("userdata/cache/"))
    model.set_seed(123)
    print(f"loading {time.monotonic() - start_load}s", file=sys.stderr)
    system_prompt = (
        "You are a helpful assistant who answers questions. "
        "If you complete a task also ask to do it again and mention how fun "
        "it was."
    )
    try:
        messages: list[ChatCompletionRequestMessage] = [
            {
                "role": "system",
                "content": system_prompt,
            },
        ]
        while True:
            set_color(CONSOLE_COLOR_USER_INPUT)
            text = input("User: ")
            set_color(CONSOLE_COLOR_DEFAULT)
            messages.append(
                {
                    "role": "user",
                    "content": text,
                })
            response: list[str] = []
            try:
                for out in model.create_chat_completion(
                        messages, max_tokens=None, stream=True):
                    resp = cast(CreateChatCompletionStreamResponse, out)
                    delta = resp["choices"][0]["delta"]
                    content: str | None = cast(str, delta.get("content", ""))
                    if content:
                        set_color(CONSOLE_COLOR_PROMPT)
                        print(content, end="")
                        set_color(CONSOLE_COLOR_DEFAULT)
                        response.append(content)
                        sys.stdout.flush()
            except KeyboardInterrupt:
                pass
            messages.append(
                {
                    "role": "assistant",
                    "content": "".join(response),
                })
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        print(CONSOLE_COLOR_DEFAULT, end="")


if __name__ == "__main__":
    run()
