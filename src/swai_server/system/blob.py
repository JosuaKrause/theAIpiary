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
from collections.abc import Iterator
from contextlib import contextmanager
from typing import IO


class BlobStorage:
    @contextmanager
    def open_blob_write(self, name: str) -> Iterator[IO[bytes]]:
        raise NotImplementedError()

    @contextmanager
    def open_blob_read(self, name: str) -> Iterator[IO[bytes]]:
        raise NotImplementedError()

    def blob_list(self, prefix: str) -> list[str]:
        raise NotImplementedError()

    def blob_remove(self, names: list[str]) -> None:
        raise NotImplementedError()
