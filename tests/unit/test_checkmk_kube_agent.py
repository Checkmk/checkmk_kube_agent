#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

"""Tests for `checkmk_kube_agent` package."""

from checkmk_kube_agent.checkmk_kube_agent import hello_world


def test_hello_world():
    """Hello world"""
    assert hello_world()
