#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

"""Cluster and node collector container metadata collection."""

from checkmk_kube_agent.type_defs import (
    CheckmkKubeAgentMetadata,
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


def parse_metadata(
    *,
    os_release_content: str,
    node: str,
    host_name: str,
    python_version: str,
    python_compiler: str,
    checkmk_kube_agent_version: str,
) -> CollectorMetadata:
    """Collector metadata: platform and checkmk_kube_agent package information
    running in current container."""
    release_content = {}
    for line in os_release_content.split("\n"):
        if not line:
            continue
        metadata_name, metadata_value = line.split("=")
        release_content[metadata_name] = metadata_value

    return CollectorMetadata(
        node=NodeName(node),
        host_name=HostName(host_name),
        container_platform=PlatformMetadata(
            os_name=OsName(release_content["ID"]),
            os_version=Version(release_content["VERSION_ID"].replace('"', "")),
            python_version=Version(python_version),
            python_compiler=PythonCompiler(python_compiler),
        ),
        checkmk_kube_agent=CheckmkKubeAgentMetadata(
            project_version=Version(checkmk_kube_agent_version)
        ),
    )


def parse_node_collector_metadata(
    collector_metadata: CollectorMetadata,
    collector_type: CollectorType,
    components: Components,
) -> NodeCollectorMetadata:
    """Node collector metadata: platform and external component metadata"""
    return NodeCollectorMetadata(
        node=collector_metadata.node,
        host_name=collector_metadata.host_name,
        container_platform=collector_metadata.container_platform,
        checkmk_kube_agent=collector_metadata.checkmk_kube_agent,
        collector_type=collector_type,
        components=components,
    )
