#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

"""Tests for Container Metadata."""

import pytest

from checkmk_kube_agent.container_metadata import (
    parse_metadata,
    parse_node_collector_metadata,
)
from checkmk_kube_agent.type_defs import (
    CheckmkKubeAgentMetadata,
    CollectorMetadata,
    NodeCollectorMetadata,
    NodeName,
    OsName,
    PlatformMetadata,
    PythonCompiler,
    Version,
)

# pylint: disable=redefined-outer-name,too-many-arguments


@pytest.fixture
def os_release_content() -> str:
    """Example content of /etc/os-release."""
    return """NAME="Alpine Linux"
ID=alpine
VERSION_ID=3.15.0
PRETTY_NAME="Alpine Linux v3.15"
HOME_URL="https://alpinelinux.org/"
BUG_REPORT_URL="https://bugs.alpinelinux.org/"

"""


def test_parse_metadata(os_release_content: str) -> None:
    """Collector metadata is parsed correctly"""
    assert parse_metadata(
        os_release_content=os_release_content,
        node="nebukadnezar",
        python_version="3.9.9",
        python_compiler="GCC",
        checkmk_kube_agent_version="0.1.0",
    ) == CollectorMetadata(
        node=NodeName("nebukadnezar"),
        container_platform=PlatformMetadata(
            os_name=OsName("alpine"),
            os_version=Version("3.15.0"),
            python_version=Version("3.9.9"),
            python_compiler=PythonCompiler("GCC"),
        ),
        checkmk_kube_agent=CheckmkKubeAgentMetadata(project_version=Version("0.1.0")),
    )


def test_parse_node_collector_metadata() -> None:
    """Node collector metadata is parsed correctly"""
    assert parse_node_collector_metadata(
        collector_metadata=CollectorMetadata(
            node=NodeName("nebukadnezar"),
            container_platform=PlatformMetadata(
                os_name=OsName("alpine"),
                os_version=Version("3.15.0"),
                python_version=Version("3.9.9"),
                python_compiler=PythonCompiler("GCC"),
            ),
            checkmk_kube_agent=CheckmkKubeAgentMetadata(
                project_version=Version("0.1.0")
            ),
        ),
        cadvisor_version="v0.40.0",
        checkmk_agent_version="2.1.0i1",
    ) == NodeCollectorMetadata(
        node=NodeName("nebukadnezar"),
        container_platform=PlatformMetadata(
            os_name=OsName("alpine"),
            os_version=Version("3.15.0"),
            python_version=Version("3.9.9"),
            python_compiler=PythonCompiler("GCC"),
        ),
        checkmk_kube_agent=CheckmkKubeAgentMetadata(project_version=Version("0.1.0")),
        cadvisor_version=Version("v0.40.0"),
        checkmk_agent_version=Version("2.1.0i1"),
    )
