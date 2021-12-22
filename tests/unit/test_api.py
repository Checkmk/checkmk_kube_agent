#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

"""Tests for cluster collector API endpoints."""

from threading import Thread
from typing import Sequence

import pytest
from fastapi.testclient import TestClient

from checkmk_kube_agent.api import (
    ContainerMetricKey,
    app,
    container_metric_key,
    parse_arguments,
)
from checkmk_kube_agent.dedup_queue import DedupQueue
from checkmk_kube_agent.type_defs import ContainerMetric, MetricCollection

# pylint: disable=redefined-outer-name


# Note: this queue is used only within the testing context. During operation, a
# queue is created with the respective user configuration at start-up. See API
# `main` function.
container_metric_queue = DedupQueue[ContainerMetricKey, ContainerMetric](
    container_metric_key,
)
app.state.container_metric_queue = container_metric_queue
CLUSTER_COLLECTOR_CLIENT = TestClient(app)


@pytest.fixture
def metric_collection() -> MetricCollection:
    """Metrics data sample"""
    return MetricCollection(
        container_metrics=[
            ContainerMetric(
                container_name=(
                    "k8s_checkmk-cluster-agent_checkmk-cluster-agent-"
                    "5c645c445f-tp44q_checkmk-monitoring_cf703718-71a1-"
                    "41de-8026-b52d3195229b_0"
                ),
                namespace="checkmk-monitoring",
                pod_uid="cf703718-71a1-41de-8026-b52d3195229b",
                pod_name="checkmk-cluster-agent-5c645c445f-tp44q",
                metric_name="container_cpu_cfs_periods_total",
                metric_value_string="4783",
            ),
            ContainerMetric(
                container_name=(
                    "k8s_POD_checkmk-worker-agent-8x8bt_checkmk-monitoring"
                    "_f560ac4c-2dd6-4d2e-8044-caaf6873ce93_0"
                ),
                namespace="checkmk-monitoring",
                pod_uid="f560ac4c-2dd6-4d2e-8044-caaf6873ce93",
                pod_name="checkmk-worker-agent-8x8bt",
                metric_name="container_memory_cache",
                metric_value_string="0",
            ),
            ContainerMetric(
                container_name=(
                    "k8s_kube-scheduler_kube-scheduler-k8_kube-system_"
                    "b58645c4b948b3629f3b7cc9f5fdde56_0"
                ),
                namespace="kube-system",
                pod_uid="b58645c4b948b3629f3b7cc9f5fdde56",
                pod_name="kube-scheduler-k8",
                metric_name="container_cpu_load_average_10s",
                metric_value_string="0 1638960637145",
            ),
        ],
        node_metrics=[],
    )


@pytest.fixture
def argv() -> Sequence[str]:
    """Cluster collector main function arguments"""
    return [
        "--host",
        "127.0.0.2",
        "--port",
        "5",
        "--secure-protocol",
        "--ssl-keyfile",
        "my-ssl-keyfile",
        "--ssl-keyfile-password",
        "123!",
        "--ssl-certfile",
        "my-ssl-certfile",
        "--queue-maxsize",
        "3",
    ]


def test_parse_arguments(argv: Sequence[str]) -> None:
    """Cluster collector arguments are parsed correctly"""
    args = parse_arguments(argv)

    assert args.host == "127.0.0.2"
    assert args.port == 5
    assert args.secure_protocol is True
    assert args.ssl_keyfile == "my-ssl-keyfile"
    assert args.ssl_keyfile_password == "123!"
    assert args.ssl_certfile == "my-ssl-certfile"
    assert args.queue_maxsize == 3


def test_root() -> None:
    """Root endpoint redirects to API documentation"""
    response = CLUSTER_COLLECTOR_CLIENT.get("/")
    assert response.status_code == 200
    assert "<title>FastAPI - Swagger UI</title>" in response.content.decode("utf-8")


def test_health() -> None:
    """API health endpoint returns status"""
    response = CLUSTER_COLLECTOR_CLIENT.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "available"}


def test_udpate_container_metrics(
    metric_collection: MetricCollection,
) -> None:
    """`update_container_metrics` endpoint writes container metric data to
    queue"""
    response = CLUSTER_COLLECTOR_CLIENT.post(
        "/update_container_metrics",
        data=metric_collection.json(),
    )
    assert response.status_code == 200
    assert (
        list(app.state.container_metric_queue.values())
        == metric_collection.container_metrics
    )


def test_send_container_metrics(
    metric_collection: MetricCollection,
) -> None:
    """`container_metrics` endpoint returns all data from queue"""
    response = CLUSTER_COLLECTOR_CLIENT.get("/container_metrics")
    assert response.status_code == 200
    assert response.json() == metric_collection.container_metrics


def test_concurrent_update_container_metrics() -> None:
    """`update_container_metrics` endpoint is able to serve concurrent post
    requests"""
    threads = []
    errored_status_codes = []

    def update_metrics():
        response = CLUSTER_COLLECTOR_CLIENT.post(
            "/update_container_metrics",
            data=MetricCollection(
                container_metrics=[],
                node_metrics=[],
            ).json(),
        )
        if response.status_code != 200:
            errored_status_codes.append(response.status_code)

    for i in range(100):  # pylint: disable=unused-variable
        threads.append(Thread(target=update_metrics))

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert not errored_status_codes


def test_concurrent_get_container_metrics() -> None:
    """`container_metrics` endpoint is able to handle concurrent get
    requests"""
    threads = []
    errored_status_codes = []

    def get_metrics():
        response = CLUSTER_COLLECTOR_CLIENT.get("/container_metrics")
        if response.status_code != 200:
            errored_status_codes.append(response.status_code)

    for i in range(100):  # pylint: disable=unused-variable
        threads.append(Thread(target=get_metrics))

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert not errored_status_codes
