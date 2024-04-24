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
import json
import sys
import time
from typing import cast, TypeAlias

from llama_cpp import (
    ChatCompletionRequestAssistantMessage,
    ChatCompletionRequestFunctionMessage,
    ChatCompletionRequestSystemMessage,
    ChatCompletionRequestToolMessage,
    ChatCompletionRequestUserMessage,
    CreateChatCompletionStreamResponse,
    Llama,
)


Message: TypeAlias = (
    ChatCompletionRequestSystemMessage
    | ChatCompletionRequestUserMessage
    | ChatCompletionRequestAssistantMessage
    | ChatCompletionRequestUserMessage
    | ChatCompletionRequestToolMessage
    | ChatCompletionRequestFunctionMessage)


def run() -> None:
    start_load = time.monotonic()
    llm = Llama(
        model_path="./models/Meta-Llama-3-8B-Instruct-IQ3_XS.gguf",
        chat_format="llama-2")
    print(f"loading {time.monotonic() - start_load}s", file=sys.stderr)
    messages: list[Message] = [
        {
            "role": "system",
            "content": "You are a helpful assistant who answers questions.",
        },
        {
            "role": "user",
            "content": (
                "Can you count to 100 skipping every number "
                "divisble by 3 or 5?"),
        },
    ]
    start_response: float | None = time.monotonic()
    for resp in llm.create_chat_completion(messages=messages, stream=True):
        if start_response is not None:
            print(
                f"first response: {time.monotonic() - start_response}s",
                file=sys.stderr)
            print("model answer:")
            start_response = None
        cur = cast(CreateChatCompletionStreamResponse, resp)
        msg = cast(str, cur["choices"][0]["delta"].get("content", ""))
        sys.stdout.write(msg)
        sys.stdout.flush()
        print(
            json.dumps(resp, indent=2, sort_keys=True),
            file=sys.stderr)


if __name__ == "__main__":
    run()
