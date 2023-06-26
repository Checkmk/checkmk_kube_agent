#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.
"""Shared functions between collectors."""

import argparse
import os
import platform
from functools import partial
from typing import Mapping, Tuple, Union

import requests
from urllib3.util.retry import Retry

import checkmk_kube_agent
from checkmk_kube_agent.container_metadata import parse_metadata
from checkmk_kube_agent.type_defs import CollectorMetadata

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


def collector_metadata() -> CollectorMetadata:  # pragma: no cover
    """Collector metadata in a container context"""

    # os-release file is read because platform, sys and os libraries return
    # metadata of the underlying machine, but container platform information
    # should be collected.
    with open("/etc/os-release", "r", encoding="utf-8") as release_file:
        release_content = release_file.read()

    return parse_metadata(
        os_release_content=release_content,
        node=os.environ["NODE_NAME"],  # env variable set by Kubernetes config
        host_name=os.environ["HOSTNAME"],  # env variable set by Kubernetes
        python_version=platform.python_version(),
        python_compiler=platform.python_compiler(),
        checkmk_kube_agent_version=checkmk_kube_agent.__version__,
    )
