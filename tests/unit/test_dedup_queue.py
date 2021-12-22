#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

"""Tests for DedupQueue."""

from copy import deepcopy
from threading import Thread
from typing import List, NamedTuple, Union

import pytest

from checkmk_kube_agent.dedup_queue import DedupQueue


class Entry(NamedTuple):  # pylint: disable=missing-class-docstring
    key: str
    value: str


def test_add_entries() -> None:
    """Elements are added to the queue using the .put method"""
    queue = DedupQueue[str, Entry](key=lambda e: e.key, maxsize=10)
    queue.put(Entry(key="fookey", value="foo"))
    queue.put(Entry(key="barkey", value="bar"))

    assert len(queue) == 2
    entries = list(queue.items())
    assert entries[0] == ("fookey", Entry(key="fookey", value="foo"))
    assert entries[1] == ("barkey", Entry(key="barkey", value="bar"))


def test_get_all_entries() -> None:
    """All entries are returned by the .get_all method, and the queue is
    cleared"""
    queue = DedupQueue[str, Entry](key=lambda e: e.key, maxsize=10)
    queue.put(Entry(key="fookey", value="foo"))
    queue.put(Entry(key="barkey", value="bar"))

    assert queue.get_all() == [
        Entry(key="fookey", value="foo"),
        Entry(key="barkey", value="bar"),
    ]
    assert len(queue) == 0


def test_add_existing_entry() -> None:
    """Existing element is deleted and reinserted"""
    queue = DedupQueue[str, Entry](key=lambda e: e.key, maxsize=10)
    queue.put(Entry(key="fookey", value="foo"))
    queue.put(Entry(key="barkey", value="bar"))

    queue.put(Entry(key="fookey", value="aardvark"))

    assert len(queue) == 2
    entries = list(queue.items())
    assert entries[0] == ("barkey", Entry(key="barkey", value="bar"))
    assert entries[1] == ("fookey", Entry(key="fookey", value="aardvark"))


def test_queue_maxsize() -> None:
    """Max size leads to the oldest element to be discarded when maxsize is
    reached"""
    queue = DedupQueue[str, str](key=lambda k: k, maxsize=3)
    queue.put("foo")
    queue.put("bar")
    queue.put("baz")
    assert len(queue) == 3

    queue.put("biz")
    assert len(queue) == 3
    entries = list(queue.values())
    assert entries[0] == "bar"
    assert entries[1] == "baz"
    assert entries[2] == "biz"


def test_queue_maxsize_add_existing_entry() -> None:
    """Maxsize implementation does not lead to deleted first element when
    attempting to add an existing element to the queue"""
    queue = DedupQueue[str, str](key=lambda k: k, maxsize=3)
    queue.put("foo")
    queue.put("bar")
    queue.put("baz")
    assert len(queue) == 3

    queue.put("bar")
    assert len(queue) == 3
    entries = list(queue.values())
    assert entries[0] == "foo"
    assert entries[1] == "baz"
    assert entries[2] == "bar"


def test_default_maxsize() -> None:
    """Default maxsize leads to a queue size limited only by resources"""
    queue = DedupQueue[int, int](key=lambda k: k)
    for i in range(100):
        queue.put(i)
    assert len(queue) == 100


def test_none_queue_maxsize() -> None:
    """Maxsize set to None leads to a queue size limited only by resources"""
    queue = DedupQueue[int, int](key=lambda k: k, maxsize=None)
    for i in range(100):
        queue.put(i)
    assert len(queue) == 100


def test_zero_queue_maxsize() -> None:
    """Zero maxsize leads to an empty queue"""
    queue = DedupQueue[str, str](key=lambda k: k, maxsize=0)
    queue.put("foo")

    assert len(queue) == 0


def test_negative_queue_maxsize() -> None:
    """Error is raised when attempting to set negative maxsize"""
    with pytest.raises(TypeError):
        DedupQueue[object, object](key=lambda k: k, maxsize=-1)


def test_concurrent_read_write() -> None:
    """Queue is thread safe: concurrent put and get operations do not lead to
    lost results or hanging threads"""
    ThreadingEntry = Union[int, object]
    queue = DedupQueue[ThreadingEntry, ThreadingEntry](key=lambda k: k)
    threads = []
    entries: List[ThreadingEntry] = list(range(1000))
    expected_entries = deepcopy(entries)
    sentinel = object()  # signal to terminate
    entries.append(sentinel)
    entries_from_queue = []

    def putter(queue):
        while entries:
            try:
                queue.put(entries.pop(0))
            except IndexError:
                continue

    def getter(queue):
        abort = False
        while not abort:
            for entry in queue.get_all():
                # Note: which thread acquires the lock at any given time is
                # random, which means the thread that adds the sentinel
                # object to the queue may not be the last thread, and thus
                # the sentinel object not the last entry. It is therefore
                # necessary to add entries to the results after the
                # sentinel object has been found.
                if entry is sentinel:
                    # The sentinel object is put back to the queue for the
                    # next thread that executes getter, so that it too can
                    # shut itself down.
                    queue.put(sentinel)
                    abort = True
                else:
                    entries_from_queue.append(entry)

    for i in range(1000):  # pylint: disable=unused-variable
        threads.append(
            Thread(
                target=putter,
                args=(queue,),
            )
        )
        threads.append(
            Thread(
                target=getter,
                args=(queue,),
            )
        )

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert expected_entries == sorted(entries_from_queue)
