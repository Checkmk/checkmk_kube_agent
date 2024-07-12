#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

"""Tests for Container Metadata."""

import json
from enum import Enum

import pytest

from checkmk_kube_agent.container_metadata import (
    parse_metadata,
    parse_node_collector_metadata,
)
from checkmk_kube_agent.type_defs import (
    CheckmkKubeAgentMetadata,
    ClusterCollectorMetadata,
    CollectorMetadata,
    CollectorType,
    Components,
    HostName,
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


@pytest.fixture
def collector_metadata() -> CollectorMetadata:
    """Metadata common to all collectors"""
    return CollectorMetadata(
        node=NodeName("nebukadnezar"),
        host_name=HostName("morpheus"),
        container_platform=PlatformMetadata(
            os_name=OsName("alpine"),
            os_version=Version("3.15.0"),
            python_version=Version("3.9.9"),
            python_compiler=PythonCompiler("GCC"),
        ),
        checkmk_kube_agent=CheckmkKubeAgentMetadata(project_version=Version("0.1.0")),
    )


def test_parse_metadata(os_release_content: str) -> None:
    """Collector metadata is parsed correctly"""
    assert parse_metadata(
        os_release_content=os_release_content,
        node="nebukadnezar",
        host_name="morpheus",
        python_version="3.9.9",
        python_compiler="GCC",
        checkmk_kube_agent_version="0.1.0",
    ) == CollectorMetadata(
        node=NodeName("nebukadnezar"),
        host_name=HostName("morpheus"),
        container_platform=PlatformMetadata(
            os_name=OsName("alpine"),
            os_version=Version("3.15.0"),
            python_version=Version("3.9.9"),
            python_compiler=PythonCompiler("GCC"),
        ),
        checkmk_kube_agent=CheckmkKubeAgentMetadata(project_version=Version("0.1.0")),
    )


def test_parse_cluster_collector_metadata(
    collector_metadata: CollectorMetadata,
) -> None:
    """Cluster collector metadata is parsed correctly based on collector
    metadata."""
    assert ClusterCollectorMetadata(
        **dict(collector_metadata)
    ) == ClusterCollectorMetadata(
        node=NodeName("nebukadnezar"),
        host_name=HostName("morpheus"),
        container_platform=PlatformMetadata(
            os_name=OsName("alpine"),
            os_version=Version("3.15.0"),
            python_version=Version("3.9.9"),
            python_compiler=PythonCompiler("GCC"),
        ),
        checkmk_kube_agent=CheckmkKubeAgentMetadata(project_version=Version("0.1.0")),
    )


def test_parse_machine_sections_collector_metadata(
    collector_metadata: CollectorMetadata,
) -> None:
    """Machine sections collector metadata is parsed correctly"""
    assert parse_node_collector_metadata(
        collector_metadata=collector_metadata,
        collector_type=CollectorType.MACHINE_SECTIONS,
        components=Components(
            cadvisor_version=None, checkmk_agent_version=Version("2.1.0i1")
        ),
    ) == NodeCollectorMetadata(
        node=NodeName("nebukadnezar"),
        host_name=HostName("morpheus"),
        container_platform=PlatformMetadata(
            os_name=OsName("alpine"),
            os_version=Version("3.15.0"),
            python_version=Version("3.9.9"),
            python_compiler=PythonCompiler("GCC"),
        ),
        checkmk_kube_agent=CheckmkKubeAgentMetadata(project_version=Version("0.1.0")),
        collector_type=CollectorType.MACHINE_SECTIONS,
        components=Components(
            cadvisor_version=None,
            checkmk_agent_version=Version("2.1.0i1"),
        ),
    )


def test_parse_machine_sections_missing_checkmk_agent_version(
    collector_metadata: CollectorMetadata,
) -> None:
    """Missing checkmk_agent_version leads to ValueError when collector type is
    Machine Sections."""
    with pytest.raises(ValueError):
        parse_node_collector_metadata(
            collector_metadata=collector_metadata,
            collector_type=CollectorType.MACHINE_SECTIONS,
            components=Components(
                cadvisor_version=None,
                checkmk_agent_version=None,
            ),
        )

    with pytest.raises(ValueError):
        parse_node_collector_metadata(
            collector_metadata=collector_metadata,
            collector_type=CollectorType.MACHINE_SECTIONS,
            components=Components(
                cadvisor_version=Version("v0.43.0"), checkmk_agent_version=None
            ),
        )


def test_parse_container_metrics_collector_metadata(
    collector_metadata: CollectorMetadata,
) -> None:
    """Container metrics collector metadata is parsed correctly"""
    assert parse_node_collector_metadata(
        collector_metadata=collector_metadata,
        collector_type=CollectorType.CONTAINER_METRICS,
        components=Components(
            cadvisor_version=Version("v0.43.0"), checkmk_agent_version=None
        ),
    ) == NodeCollectorMetadata(
        node=NodeName("nebukadnezar"),
        host_name=HostName("morpheus"),
        container_platform=PlatformMetadata(
            os_name=OsName("alpine"),
            os_version=Version("3.15.0"),
            python_version=Version("3.9.9"),
            python_compiler=PythonCompiler("GCC"),
        ),
        checkmk_kube_agent=CheckmkKubeAgentMetadata(project_version=Version("0.1.0")),
        collector_type=CollectorType.CONTAINER_METRICS,
        components=Components(
            cadvisor_version=Version("v0.43.0"),
            checkmk_agent_version=None,
        ),
    )


def test_parse_container_metrics_missing_cadvisor_version(
    collector_metadata: CollectorMetadata,
) -> None:
    """Missing cadvisor_version leads to ValueError when collector type is
    Container Metrics."""
    with pytest.raises(ValueError):
        parse_node_collector_metadata(
            collector_metadata=collector_metadata,
            collector_type=CollectorType.CONTAINER_METRICS,
            components=Components(
                cadvisor_version=None,
                checkmk_agent_version=None,
            ),
        )

    with pytest.raises(ValueError):
        parse_node_collector_metadata(
            collector_metadata=collector_metadata,
            collector_type=CollectorType.CONTAINER_METRICS,
            components=Components(
                cadvisor_version=None, checkmk_agent_version=Version("2.1.0i1")
            ),
        )


def test_invalid_collector_type() -> None:
    """Unknown collector type raises ValueError"""
    collector_metadata = CollectorMetadata(
        node=NodeName("nebukadnezar"),
        host_name=HostName("morpheus"),
        container_platform=PlatformMetadata(
            os_name=OsName("alpine"),
            os_version=Version("3.15.0"),
            python_version=Version("3.9.9"),
            python_compiler=PythonCompiler("GCC"),
        ),
        checkmk_kube_agent=CheckmkKubeAgentMetadata(project_version=Version("0.1.0")),
    )

    class CollectorType(Enum):  # pylint: disable=missing-class-docstring
        UNKNOWN_TYPE = "Foo"

    with pytest.raises(ValueError):
        parse_node_collector_metadata(
            collector_metadata=collector_metadata,
            collector_type=CollectorType.UNKNOWN_TYPE,  # type: ignore
            components=Components(
                cadvisor_version=Version("v0.43.0"), checkmk_agent_version=None
            ),
        )


def test_node_collector_metadata_serialisation() -> None:
    """Metadata can successfully be (de)serialised"""
    metadata = NodeCollectorMetadata(
        node=NodeName("nebukadnezar"),
        host_name=HostName("morpheus"),
        container_platform=PlatformMetadata(
            os_name=OsName("alpine"),
            os_version=Version("3.15.0"),
            python_version=Version("3.9.9"),
            python_compiler=PythonCompiler("GCC"),
        ),
        checkmk_kube_agent=CheckmkKubeAgentMetadata(project_version=Version("0.1.0")),
        collector_type=CollectorType.CONTAINER_METRICS,
        components=Components(
            cadvisor_version=Version("v0.43.0"), checkmk_agent_version=None
        ),
    )

    assert NodeCollectorMetadata(**json.loads(metadata.json())) == metadata
