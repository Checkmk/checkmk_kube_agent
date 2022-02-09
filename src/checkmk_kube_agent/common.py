#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.
"""Shared functions between collectors."""

import argparse
from functools import partial
from typing import Mapping, Tuple, Union

import requests
from urllib3.util.retry import Retry  # type: ignore[import]

TCPTimeout = Union[None, int, Tuple[int, int]]


def collector_argument_parser(**kwargs) -> argparse.ArgumentParser:
    """Argument parser pre-populated with shared arguments and shared
    defaults."""

    parser = argparse.ArgumentParser(**kwargs)

    parser.add_argument(
        "--host",
        "-s",
        help="Host IP address of the cluster collector API",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        help="Host port of the cluster collector API",
    )
    parser.add_argument(
        "--secure-protocol",
        action="store_true",
        help="Use secure protocol (HTTPS)",
    )
    parser.add_argument(
        "--max-retries",
        "-r",
        type=int,
        help="Maximum number of retries on connection error",
    )
    parser.add_argument(
        "--connect-timeout",
        type=int,
        help="Time in seconds to wait for a TCP connection",
    )
    parser.add_argument(
        "--read-timeout",
        type=int,
        help="Time in seconds to wait for a response from the counterpart "
        "during a TCP connection",
    )

    parser.set_defaults(
        connect_timeout=10,
        read_timeout=12,
    )

    return parser


def tcp_session(  # pylint: disable=dangerous-default-value
    *,
    retries: int = 3,
    backoff_factor: float = 1.0,
    timeout: TCPTimeout = None,
    headers: Mapping[str, str] = {},
) -> requests.Session:
    """Pre-configured TCP session."""

    session = requests.Session()

    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
    )

    session.mount("http://", requests.adapters.HTTPAdapter(max_retries=retry))
    session.mount("https://", requests.adapters.HTTPAdapter(max_retries=retry))

    session.headers.update({"ContentType": "application/json"})
    session.headers.update(headers)

    session.request = partial(session.request, timeout=timeout)  # type: ignore

    return session
