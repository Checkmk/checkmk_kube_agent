#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

"""DedupTTLCache to store data in RAM. Deduplicates entries based on a key
function and adds thread safety to TTLCache."""

from threading import Lock
from typing import Callable, Sequence, TypeVar

from cachetools import TTLCache

K = TypeVar("K")  # pylint: disable=invalid-name
V = TypeVar("V")  # pylint: disable=invalid-name


class DedupTTLCache(TTLCache[K, V]):
    """Thread-safe deduplicating TTL cache.

    WARNING: This code requires Python >= 3.7 to work.

    Deduplication is achieved by overwriting existing entries that are to be
    deduplicated with the new value when `put` is called.

    The key of the entry that signals its unique identity is determined by a
    key function, specified by the `key` argument.

    When provided with a `maxsize`, any entry added that causes the cache to
    grow beyond this size will lead to the oldest entry to be discarded from
    the cache.

    When provided with a `ttl` (time to live in seconds), entries that exceed
    this age are not returned by `get_all` or `get` methods, and are removed
    from the cache eventually.

    It is not recommended to change `maxsize` or `ttl` during operation.
    Do so at your own risk.

    Examples:

        >>> c = DedupTTLCache(key=lambda x: x[0], maxsize=2, ttl=2*60)
        >>> c.put(("foo", "bar"))
        >>> c.put(("foo", "bar"))
        >>> c
        DedupTTLCache({'foo': ('foo', 'bar')}, maxsize=2, currsize=1)

        >>> c.put(("bar", "foo"))
        >>> c.put(("baz", "foo"))
        >>> c
        DedupTTLCache({'bar': ('bar', 'foo'), 'baz': ('baz', 'foo')}, maxsize=2, currsize=2)

        >>> c.get_all()
        [('bar', 'foo'), ('baz', 'foo')]
    """

    def __init__(
        self,
        *,
        key: Callable[[V], K],
        maxsize: int = 10000000,
        ttl: int = 60 * 60 * 24 * 365,
    ):
        if maxsize <= 0:
            raise ValueError(f"maxsize must be at least 1, got {maxsize}")
        if ttl <= 0:
            raise ValueError(f"ttl must be at least 1, got {ttl}")

        super().__init__(maxsize=maxsize, ttl=ttl)
        self.key = key
        self.__lock = Lock()

    def put(self, entry: V):
        """Add entries to the TTL cache.

        New entries overwrite existing entries based on a key determined by the
        configured key function. If maxsize is configured and reached, the
        oldest entry is discarded before a new entry is added."""
        key = self.key(entry)
        with self.__lock:
            self[key] = entry

    def get_all(self) -> Sequence[V]:
        """Get all entries from the TTL cache."""
        with self.__lock:
            return list(self.values())
