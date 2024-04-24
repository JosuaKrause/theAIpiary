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
from typing import Generic, overload, TypeVar


ANSI_COLOR_RESET = "\x1b[0m"
ANSI_COLOR_YELLOW = "\x1b[33m"
ANSI_BOLD = "\x1b[1m"
ANSI_COLOR_GREEN = "\x1b[32m"

CONSOLE_COLOR_DEFAULT = ANSI_COLOR_RESET
CONSOLE_COLOR_PROMPT = ANSI_COLOR_YELLOW
CONSOLE_COLOR_USER_INPUT = ANSI_BOLD + ANSI_COLOR_GREEN


T = TypeVar('T')


# Iterative search
# Actively searches and prevents a pattern from being returned
class IterSearch(Generic[T]):  # pylint: disable=too-few-public-methods
    def __init__(self, pattern: list[T]) -> None:
        self.pattern = list(pattern)
        self.buffer: list[T] = []

    def __call__(self, char: T) -> list[T]:
        self.buffer += [char]

        if self.pattern[:len(self.buffer)] == self.buffer:
            if len(self.buffer) >= len(self.pattern):
                self.buffer.clear()
            return []

        _tmp = self.buffer[:]
        self.buffer.clear()
        return _tmp


class Circle(Generic[T]):
    def __init__(self, size: int, *, default: T) -> None:
        self.list: list[T] = [default] * size
        self.maxsize = size
        self.size = 0
        self.offset = 0

    def append(self, elem: T) -> None:
        if self.size < self.maxsize:
            self.list[self.size] = elem
            self.size += 1
        else:
            self.list[self.offset] = elem
            self.offset = (self.offset + 1) % self.maxsize

    @overload
    def __getitem__(self, val: int) -> T:
        ...

    @overload
    def __getitem__(self, val: slice) -> list[T]:
        ...

    def __getitem__(self, val: int | slice) -> T | list[T]:
        if isinstance(val, int):
            if 0 > val or val >= self.size:
                raise IndexError("Index out of range")
            if self.size < self.maxsize:
                return self.list[val]
            return self.list[(self.offset + val) % self.maxsize]
        if isinstance(val, slice):
            start, stop, step = val.start, val.stop, val.step
            if step is None:
                step = 1
            if start is None:
                start = 0
            if stop is None:
                stop = self.size
            if start < 0:
                start = self.size + start
            if stop < 0:
                stop = self.size + stop

            indices = range(start, stop, step)
            return [
                self.list[(self.offset + ix) % self.maxsize]
                for ix in indices
                if ix < self.size
            ]
        raise TypeError("Invalid argument type")


if __name__ == "__main__":
    c = Circle(5, default=0)

    c.append(1)
    print(c.list)
    print(c[:])
    assert c[0] == 1
    assert c[:5] == [1]

    for i in range(2, 5+1):
        c.append(i)
    print(c.list)
    print(c[:])
    assert c[0] == 1
    assert c[:5] == [1, 2, 3, 4, 5]

    for i in range(5+1, 9+1):
        c.append(i)
    print(c.list)
    print(c[:])
    assert c[0] == 5
    assert c[:5] == [5, 6, 7, 8, 9]
    # assert c[:-5] == [5, 6, 7, 8, 9]
    assert c[:10] == [5, 6, 7, 8, 9]
