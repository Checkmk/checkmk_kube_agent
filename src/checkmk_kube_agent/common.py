#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.
"""Shared functions between collectors."""

import argparse


def collector_argument_parser(**kwargs) -> argparse.ArgumentParser:
    """Argument parser pre-populated with shared arguments."""

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

    return parser
