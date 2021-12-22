#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

"""DedupQueue to store data in RAM. Deduplicates entries based on a key
function."""

from threading import Lock
from typing import Callable, Dict, Optional, Sequence, TypeVar

K = TypeVar("K")  # pylint: disable=invalid-name
V = TypeVar("V")  # pylint: disable=invalid-name


class DedupQueue(Dict[K, V]):
    """Thread-safe deduplicating queue.

    WARNING: This code requires Python >= 3.7 to work.

    Deduplication is achieved by overwriting existing entries that are to be
    deduplicated with the new value when `put` is called. The original entry is
    replaced and moved to the back of the queue.

    The key of the entry that signals its unique identity is determined by a
    key function, specified by the `key` argument.

    When provided with a `maxsize`, any entry added that causes the queue to
    grow beyond this size will lead to the oldest entry to be discarded from
    the queue.

    It is not recommended to change maxsize during operation.
    Do so at your own risk.

    Examples:

        >>> q = DedupQueue(lambda x: x[0], maxsize=2)
        >>> q.put(("foo", "bar"))
        >>> q.put(("foo", "bar"))
        >>> q
        {'foo': ('foo', 'bar')}


        >>> q.put(("bar", "foo"))
        >>> q.put(("baz", "foo"))
        >>> q
        {'bar': ('bar', 'foo'), 'baz': ('baz', 'foo')}

        >>> q.get_all()
        [('bar', 'foo'), ('baz', 'foo')]

        >>> q
        {}
    """

    __slots__ = ("key", "maxsize", "lock")

    def __init__(
        self,
        key: Callable[[V], K],
        maxsize: Optional[int] = None,
    ) -> None:

        if maxsize is not None and maxsize < 0:
            raise TypeError("maxsize must be a positive integer")

        super().__init__()
        self.key = key
        self.maxsize = maxsize
        self.lock = Lock()

    def put(self, entry: V) -> None:
        """Add entries to the queue.

        New entries overwrite existing entries based on a key determined by the
        configured key function. If maxsize is configured and reached, the
        oldest entry is discarded before a new entry is added."""
        with self.lock:
            if self.maxsize == 0:
                return

            entry_key = self.key(entry)
            if self.maxsize is not None and entry_key not in self:
                # If entry is already in the dict, the enqueue() call will not
                # result in an increase of number of elements, as the element
                # will be overwritten.
                if len(self) >= self.maxsize:
                    # The oldest key is the first one which was inserted.
                    del self[next(iter(self))]

            elif entry_key in self:
                del self[entry_key]

            self[entry_key] = entry

    def get_all(self) -> Sequence[V]:
        """Get all entries from the queue, and clear its conents
        immediately."""
        with self.lock:
            values = list(self.values())
            self.clear()
        return values
