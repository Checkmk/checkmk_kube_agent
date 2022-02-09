#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

"""Tests for Node Collector."""

from typing import Sequence

import pytest

from checkmk_kube_agent.send_metrics import parse_arguments, parse_raw_response
from checkmk_kube_agent.type_defs import ContainerMetric, MetricCollection, Timestamp

# pylint: disable=redefined-outer-name


@pytest.fixture
def commentary_text() -> str:
    """Examples of commentary text."""
    return "# HELP cadvisor_version_info\n# TYPE cadvisor_version_info gauge\n"


@pytest.fixture
def cadvisor_version_info_text() -> str:
    """First metric shown is cAdvisor version information.

    It returns a metric with a constant 1 and version information as labels.
    """
    return (
        'cadvisor_version_info{cadvisorRevision="de723a09",'
        'cadvisorVersion="v0.30.2",'
        'dockerVersion="20.10.7",'
        'kernelVersion="5.8.0-59-generic",'
        'osVersion="Alpine Linux v3.7"} 1\n'
    )


@pytest.fixture
def container_metric_empty_label() -> str:
    """Container metric with missing labels"""
    return "container_tasks_state{} 0\n"


@pytest.fixture
def container_metrics() -> str:
    """Container metrics examples"""
    return (
        "container_cpu_cfs_periods_total{"
        'container_label_addonmanager_kubernetes_io_mode="",'
        "container_label_annotation_io_kubernetes_container_ports="
        '"[{\\"name\\":\\"http\\",\\"containerPort\\":8080,\\"protocol\\":\\'
        '"TCP\\"}]",'
        "container_label_annotation_io_kubernetes_container_terminationMessage"
        'Path="/dev/termination-log",'
        'container_label_io_kubernetes_pod_name="checkmk-worker-agent-8x8bt",'
        'container_label_io_kubernetes_pod_namespace="checkmk-monitoring",'
        "container_label_io_kubernetes_pod_uid="
        '"f560ac4c-2dd6-4d2e-8044-caaf6873ce93",'
        "name="
        '"k8s_POD_checkmk-worker-agent-8x8bt_checkmk-monitoring_f560ac4c-2dd6-'
        '4d2e-8044-caaf6873ce93_0"'
        "} 5994\n"
        "container_fs_io_time_seconds_total{"
        "container_label_annotation_kubernetes_io_config_seen="
        '"2021-07-13T10:50:38.489719870Z",'
        'container_label_io_kubernetes_pod_name="kube-proxy-kvkls",'
        'container_label_io_kubernetes_pod_namespace="kube-system",'
        'container_label_io_kubernetes_pod_uid="e729f03e-59ae-444c-a835-'
        '021a919d7898",'
        'name="k8s_POD_kube-proxy-kvkls_kube-system_e729f03e-59ae-444c-a835-'
        '021a919d7898_1"'
        "} 0\n"
    )


@pytest.fixture
def system_container_metrics() -> str:
    """System container metric example"""
    return (
        "container_cpu_load_average_10s{"
        'container_label_annotation_io_kubernetes_container_hash="f4b1b257",'
        'container_label_io_kubernetes_pod_name="etcd-k8",'
        'container_label_io_kubernetes_pod_namespace="kube-system",'
        # Due to a bug in cAdvisor, the pod UID shown here is not the pod UID,
        # but the kubernetes.io/config.hash in the metadata.annotations field
        'container_label_io_kubernetes_pod_uid="f50a3637ec9e7cb947095117b393e4be",'
        'name="k8s_etcd_etcd-k8_kube-system_f50a3637ec9e7cb947095117b393e4be_0"'
        # Two values being shown instead of one also looks like a bug
        "} 0 1638960636719"
    )


@pytest.fixture
def argv() -> Sequence[str]:
    """Node collector main function arguments"""
    return [
        "--host",
        "8.8.8.8",
        "--port",
        "88",
        "--secure-protocol",
        "--polling-interval",
        "60",
        "--max-retries",
        "20",
    ]


def test_parse_arguments(argv: Sequence[str]) -> None:
    """Node collector arguments are parsed correctly"""
    args = parse_arguments(argv)

    assert args.host == "8.8.8.8"
    assert args.port == 88
    assert args.secure_protocol is True
    assert args.polling_interval == 60
    assert args.max_retries == 20


def test_parse_raw_response_skip_comments(commentary_text: str) -> None:
    """Commentary text is skipped"""
    assert parse_raw_response(commentary_text, Timestamp(0.0)) == MetricCollection(
        container_metrics=[],
    )


def test_parse_raw_response_cadvisor_version(
    cadvisor_version_info_text: str,
) -> None:
    """cAdvisor version information is not shown in container_metrics"""
    assert parse_raw_response(
        cadvisor_version_info_text, Timestamp(0.0)
    ) == MetricCollection(
        container_metrics=[],
    )


def test_parse_raw_response_empty_labels(
    container_metric_empty_label: str,
) -> None:
    """Empty labels do not lead to an exception and the container metric is
    discarded"""
    assert parse_raw_response(
        container_metric_empty_label, Timestamp(0.0)
    ) == MetricCollection(
        container_metrics=[],
    )


def test_parse_raw_response(container_metrics: str) -> None:
    """Container metrics are parsed properly into the expected schema"""
    assert parse_raw_response(container_metrics, Timestamp(0.0)) == MetricCollection(
        container_metrics=[
            ContainerMetric(
                container_name=(
                    "k8s_POD_checkmk-worker-agent-8x8bt_checkmk-"
                    "monitoring_f560ac4c-2dd6-4d2e-8044-caaf6873ce93_0"
                ),
                namespace="checkmk-monitoring",
                pod_uid="f560ac4c-2dd6-4d2e-8044-caaf6873ce93",
                pod_name="checkmk-worker-agent-8x8bt",
                metric_name="container_cpu_cfs_periods_total",
                metric_value_string="5994",
                timestamp=0.0,
            ),
            ContainerMetric(
                container_name=(
                    "k8s_POD_kube-proxy-kvkls_kube-system_e729f03e-"
                    "59ae-444c-a835-021a919d7898_1"
                ),
                namespace="kube-system",
                pod_uid="e729f03e-59ae-444c-a835-021a919d7898",
                pod_name="kube-proxy-kvkls",
                metric_name="container_fs_io_time_seconds_total",
                metric_value_string="0",
                timestamp=0.0,
            ),
        ]
    )


def test_parse_raw_response_system_containers(
    system_container_metrics: str,
) -> None:
    """System container metrics are parsed properly into the expected schema"""
    assert parse_raw_response(
        system_container_metrics, Timestamp(0.0)
    ) == MetricCollection(
        container_metrics=[
            ContainerMetric(
                container_name="k8s_etcd_etcd-k8_kube-system_f50a3637ec9e7cb947095117b393e4be_0",
                namespace="kube-system",
                # Due to a bug in cAdvisor, the pod UID shown here is not the
                # pod UID, but the kubernetes.io/config.hash in the
                # metadata.annotations field
                pod_uid="f50a3637ec9e7cb947095117b393e4be",
                pod_name="etcd-k8",
                metric_name="container_cpu_load_average_10s",
                metric_value_string="0",
                timestamp=1638960636.719,
            )
        ]
    )
