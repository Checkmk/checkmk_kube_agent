#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

"""Tests for DedupTTLCache."""

import time
from copy import deepcopy
from threading import Thread
from typing import Mapping, NamedTuple, Sequence

import pytest

from checkmk_kube_agent.dedup_ttl_cache import DedupTTLCache

# pylint: disable=redefined-outer-name


class Entry(NamedTuple):  # pylint: disable=missing-class-docstring
    key: str
    value: str


@pytest.fixture
def dedup_ttl_cache() -> DedupTTLCache:
    """Empty TTL cache"""
    cache = DedupTTLCache[str, Entry](key=lambda e: e.key, maxsize=10, ttl=120)

    assert dict(cache) == {}

    return cache


@pytest.fixture
def entries() -> Sequence[Entry]:
    """Example entries to dedup_ttl_cache"""
    return [
        Entry(key="fookey", value="foo"),
        Entry(key="barkey", value="bar"),
    ]


@pytest.fixture
def cache_content() -> Mapping[str, Entry]:
    """Cache content corresponding to entries"""
    return {
        "fookey": Entry(key="fookey", value="foo"),
        "barkey": Entry(key="barkey", value="bar"),
    }


@pytest.fixture
def maxsize_entries() -> Sequence[str]:
    """Example entries to maxsized_dedup_ttl_cache"""
    return ["foo", "bar", "baz"]


@pytest.fixture
def maxsized_dedup_ttl_cache(maxsize_entries: Sequence[str]) -> DedupTTLCache:
    """TTL cache with maximum number of entries"""
    maxsize = len(maxsize_entries)
    cache = DedupTTLCache[str, str](key=lambda k: k, maxsize=maxsize, ttl=120)

    for entry in maxsize_entries:
        cache.put(entry)

    assert cache.currsize == maxsize

    return cache


def test_add_entries(
    dedup_ttl_cache: DedupTTLCache,
    entries: Sequence[Entry],
    cache_content: Mapping[str, Entry],
) -> None:
    """Elements are added to the cache using the .put method"""
    for entry in entries:
        dedup_ttl_cache.put(entry)

    assert dedup_ttl_cache.currsize == len(entries)
    assert dict(dedup_ttl_cache) == cache_content


def test_get_all_entries(
    dedup_ttl_cache: DedupTTLCache,
    entries: Sequence[Entry],
) -> None:
    """All entries are returned by the .get_all method"""
    for entry in entries:
        dedup_ttl_cache.put(entry)

    assert dedup_ttl_cache.get_all() == entries


def test_add_existing_entry(
    dedup_ttl_cache: DedupTTLCache,
    entries: Sequence[Entry],
) -> None:
    """Existing element is overwritten"""
    for entry in entries:
        dedup_ttl_cache.put(entry)

    dedup_ttl_cache.put(Entry(key="fookey", value="aardvark"))

    assert dedup_ttl_cache.currsize == len(entries)
    assert dict(dedup_ttl_cache) == {
        "fookey": Entry(key="fookey", value="aardvark"),
        "barkey": Entry(key="barkey", value="bar"),
    }


def test_dedup_ttl_cache_maxsize(
    maxsized_dedup_ttl_cache: DedupTTLCache,
    maxsize_entries: Sequence[str],
) -> None:
    """Max size leads to the oldest element to be discarded when maxsize is
    reached"""
    maxsized_dedup_ttl_cache.put("biz")
    assert maxsized_dedup_ttl_cache.currsize == len(maxsize_entries)
    assert list(maxsized_dedup_ttl_cache.values()) == list(maxsize_entries[1:]) + [
        "biz"
    ]


def test_dedup_ttl_cache_ttl() -> None:
    """Entries exceeding time to live (seconds) are not returned"""
    cache = DedupTTLCache[str, str](key=lambda k: k, ttl=1)
    cache.put("foo")
    time.sleep(1)
    cache.put("bar")

    assert cache.get_all() == ["bar"]


def test_default_maxsize() -> None:
    """Default maxsize"""
    cache = DedupTTLCache[object, object](key=lambda k: k, ttl=120)
    assert cache.maxsize == 10000000


def test_zero_cache_maxsize() -> None:
    """Zero maxsize leads to an exception"""
    with pytest.raises(ValueError) as exception:
        DedupTTLCache[object, object](key=lambda k: k, maxsize=0, ttl=120)
    assert str(exception.value) == "maxsize must be at least 1, got 0"


def test_negative_cache_maxsize() -> None:
    """Negative maxsize leads to an exception"""
    with pytest.raises(ValueError) as exception:
        DedupTTLCache[object, object](key=lambda k: k, maxsize=-1, ttl=120)
    assert str(exception.value) == "maxsize must be at least 1, got -1"


def test_default_ttl() -> None:
    """Default ttl"""
    cache = DedupTTLCache[object, object](key=lambda k: k, maxsize=10)
    assert cache.ttl == 60 * 60 * 24 * 365


def test_zero_cache_ttl() -> None:
    """Zero maxsize leads to an exception"""
    with pytest.raises(ValueError) as exception:
        DedupTTLCache[object, object](key=lambda k: k, maxsize=10, ttl=0)
    assert str(exception.value) == "ttl must be at least 1, got 0"


def test_negative_cache_ttl() -> None:
    """Negative maxsize leads to an exception"""
    with pytest.raises(ValueError) as exception:
        DedupTTLCache[object, object](key=lambda k: k, maxsize=10, ttl=-1)
    assert str(exception.value) == "ttl must be at least 1, got -1"


def test_concurrent_read_write() -> None:
    """Cache is thread safe: concurrent put and get operations do not lead to
    hanging threads"""
    cache = DedupTTLCache[int, int](key=lambda k: k, maxsize=5000, ttl=120)
    threads = []
    entries = list(range(100))
    expected_entries = deepcopy(entries)

    def putter(cache):
        while entries:
            try:
                cache.put(entries.pop(0))
            except IndexError:
                continue

    def getter(cache):
        cache.get_all()

    for i in range(100):  # pylint: disable=unused-variable
        threads.append(
            Thread(
                target=putter,
                args=(cache,),
            )
        )
        threads.append(
            Thread(
                target=getter,
                args=(cache,),
            )
        )

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert expected_entries == sorted(cache.get_all())
