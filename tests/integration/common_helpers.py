#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2022 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

"""This file contains duplicate code from checkmk_kube_agent as the integration-tests
job is currently missing the source package. This module should be removed once this
is resolved
"""

# pylint: skip-file

from functools import partial
from typing import Mapping, Tuple, Union

import requests
from urllib3 import Retry

TCPTimeout = Union[None, int, Tuple[int, int]]


def tcp_session(  # pylint: disable=dangerous-default-value, duplicate-code
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
