#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

"""Cluster collector API data type definitions."""

from typing import NewType, Sequence

from pydantic import BaseModel

LabelValue = NewType("LabelValue", str)
ContainerName = NewType("ContainerName", LabelValue)
MetricName = NewType("MetricName", str)
MetricValueString = NewType("MetricValueString", str)
Namespace = NewType("Namespace", LabelValue)
PodUid = NewType("PodUid", LabelValue)
PodName = NewType("PodName", LabelValue)

# pylint: disable=missing-class-docstring
# pylint: disable=too-few-public-methods


class ContainerMetric(BaseModel):
    container_name: ContainerName
    namespace: Namespace
    pod_uid: PodUid
    pod_name: PodName
    metric_name: MetricName
    metric_value_string: MetricValueString


class MetricCollection(BaseModel):
    container_metrics: Sequence[ContainerMetric]
