#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

"""Cluster collector API data type definitions."""

from enum import Enum
from typing import NamedTuple, NewType, NoReturn, Optional, Protocol, Sequence

from pydantic import BaseModel, root_validator

LabelName = NewType("LabelName", str)
LabelValue = NewType("LabelValue", str)
ContainerName = NewType("ContainerName", LabelValue)
HostName = NewType("HostName", str)
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
# pylint: disable=missing-function-docstring
# pylint: disable=too-few-public-methods
# pylint: disable=no-self-argument
# pylint: disable=no-self-use


class ContainerMetric(BaseModel):
    container_name: ContainerName
    namespace: Namespace
    pod_uid: PodUid
    pod_name: PodName
    metric_name: MetricName
    metric_value_string: MetricValueString
    timestamp: Timestamp


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
    host_name: HostName  # This looks like the pod name, but it is not. It is
    # possible to give the host an arbitrary host name, different from the pod
    # name which is managed by Kubernetes.
    container_platform: PlatformMetadata
    checkmk_kube_agent: CheckmkKubeAgentMetadata


class ClusterCollectorMetadata(CollectorMetadata):
    pass


class CollectorType(Enum):
    CONTAINER_METRICS = "Container Metrics"
    MACHINE_SECTIONS = "Machine Sections"

    @classmethod
    def __get_validators__(cls):
        cls.lookup = {v: k.value for v, k in cls.__members__.items()}
        yield cls.validate

    @classmethod
    def validate(cls, value):
        if isinstance(value, str):
            value = cls(value)
        if not (lookup_value := cls.lookup.get(value.name)):
            raise ValueError(f"invalid collector type: {lookup_value}")
        return lookup_value


class Components(BaseModel):
    cadvisor_version: Optional[Version]
    checkmk_agent_version: Optional[Version]


class NodeCollectorMetadata(CollectorMetadata):
    collector_type: CollectorType
    components: Components

    @root_validator()
    def validate_components(cls, values):
        components = dict(values["components"])
        collector_type = CollectorType(values.get("collector_type"))
        # pylint: disable=fixme
        # TODO: could be refactored to match expression as soon as it is
        # supported by mypy
        if collector_type is CollectorType.CONTAINER_METRICS:
            if components["cadvisor_version"] is None:
                raise ValueError("cadvisor_version must be set")
            return values
        if collector_type is CollectorType.MACHINE_SECTIONS:
            if components["checkmk_agent_version"] is None:
                raise ValueError("checkmk_agent_version must be set")
            return values
        raise ValueError(  # pragma: no cover
            f"Unknown collector type: {collector_type}"
        )


class Metadata(BaseModel):
    cluster_collector_metadata: ClusterCollectorMetadata
    node_collector_metadata: Sequence[NodeCollectorMetadata]


class MetricCollection(BaseModel):
    container_metrics: Sequence[ContainerMetric]
    metadata: NodeCollectorMetadata


class MachineSectionsCollection(BaseModel):
    sections: MachineSections
    metadata: NodeCollectorMetadata


class UserInfo(BaseModel):
    username: str = ""  # username might be missing, so we avoid `None` value


class TokenReviewStatus(BaseModel):
    user: Optional[UserInfo]
    authenticated: bool = False


class TokenReview(BaseModel):
    status: TokenReviewStatus


class TokenError(NamedTuple):
    status_code: int
    message: str
    exception: Optional[Exception] = None


class RaiseFromError(Protocol):
    def __call__(
        self,
        token_review_response: bytes,
        token: str,
        token_error: TokenError,
    ) -> NoReturn:  # pragma: no cover
        ...


class Response(NamedTuple):
    status_code: int
    content: bytes
