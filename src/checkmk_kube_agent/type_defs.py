#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

"""Cluster collector API data type definitions."""

from typing import NewType, Sequence

from pydantic import BaseModel

LabelName = NewType("LabelName", str)
LabelValue = NewType("LabelValue", str)
ContainerName = NewType("ContainerName", LabelValue)
MetricName = NewType("MetricName", str)
MetricValueString = NewType("MetricValueString", str)
Namespace = NewType("Namespace", LabelValue)
NodeName = NewType("NodeName", str)
OsName = NewType("OsName", str)
PodUid = NewType("PodUid", LabelValue)
PodName = NewType("PodName", LabelValue)
PythonCompiler = NewType("PythonCompiler", str)
Timestamp = NewType("Timestamp", float)
Version = NewType("Version", str)

# pylint: disable=missing-class-docstring
# pylint: disable=too-few-public-methods


class ContainerMetric(BaseModel):
    container_name: ContainerName
    namespace: Namespace
    pod_uid: PodUid
    pod_name: PodName
    metric_name: MetricName
    metric_value_string: MetricValueString
    timestamp: Timestamp


class MetricCollection(BaseModel):
    container_metrics: Sequence[ContainerMetric]


class MachineSections(BaseModel):
    node_name: NodeName
    sections: str


class PlatformMetadata(BaseModel):
    os_name: OsName
    os_version: Version
    python_version: Version
    python_compiler: PythonCompiler


class CheckmkKubeAgentMetadata(BaseModel):
    project_version: Version


class CollectorMetadata(BaseModel):
    node: NodeName
    container_platform: PlatformMetadata
    checkmk_kube_agent: CheckmkKubeAgentMetadata


class ClusterCollectorMetadata(CollectorMetadata):
    pass


class NodeCollectorMetadata(CollectorMetadata):
    cadvisor_version: Version
    checkmk_agent_version: Version


class Metadata(BaseModel):
    cluster_collector_metadata: ClusterCollectorMetadata
    node_collector_metadata: Sequence[NodeCollectorMetadata]
