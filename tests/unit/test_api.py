#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

"""Tests for cluster collector API endpoints."""

import json
from threading import Thread
from typing import Sequence

import pytest
import requests
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

import checkmk_kube_agent.api
from checkmk_kube_agent.api import (
    ContainerMetricKey,
    app,
    authenticate,
    authenticate_get,
    authenticate_post,
    container_metric_key,
    parse_arguments,
)
from checkmk_kube_agent.dedup_ttl_cache import DedupTTLCache
from checkmk_kube_agent.type_defs import ContainerMetric, MetricCollection

# pylint: disable=redefined-outer-name


@pytest.fixture(scope="module")
def cluster_collector_client():
    """Cluster collector API test client"""
    # Note: this queue is used only within the testing context. During
    # operation, a queue is created with the respective user configuration at
    # start-up. See API `main` function.
    container_metric_queue = DedupTTLCache[ContainerMetricKey, ContainerMetric](
        key=container_metric_key,
        maxsize=10000,
        ttl=120,
    )
    app.state.container_metric_queue = container_metric_queue

    def authenticate() -> str:
        return ""

    app.dependency_overrides[authenticate_post] = authenticate
    app.dependency_overrides[authenticate_get] = authenticate

    app.state.writer_whitelist = {"checkmk-monitoring:node-collector"}
    app.state.reader_whitelist = {"checkmk-monitoring:checkmk-server"}

    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_read_api_token(monkeypatch: pytest.MonkeyPatch):
    """Patch Kubernetes token file read"""

    def mock_read_token():
        return ""

    monkeypatch.setattr(checkmk_kube_agent.api, "read_api_token", mock_read_token)


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
                timestamp=0.0,
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
                timestamp=0.0,
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
                metric_value_string="0",
                timestamp=1638960637.145,
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
        "--cache-maxsize",
        "3",
        "--cache-ttl",
        "400",
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
    assert args.cache_maxsize == 3
    assert args.cache_ttl == 400


def test_root(cluster_collector_client) -> None:
    """Root endpoint redirects to API documentation"""
    response = cluster_collector_client.get(
        "/",
        headers={
            "Authorization": "Bearer superdupertoken",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert "<title>FastAPI - Swagger UI</title>" in response.content.decode("utf-8")


def test_health(cluster_collector_client) -> None:
    """API health endpoint returns status"""
    response = cluster_collector_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "available"}


def test_udpate_container_metrics(
    metric_collection: MetricCollection,
    cluster_collector_client,
) -> None:
    """`update_container_metrics` endpoint writes container metric data to
    queue"""
    response = cluster_collector_client.post(
        "/update_container_metrics",
        headers={
            "Authorization": "Bearer superduperwritertoken",
            "Content-Type": "application/json",
        },
        data=metric_collection.json(),
    )
    assert response.status_code == 200
    assert (
        list(app.state.container_metric_queue.values())
        == metric_collection.container_metrics
    )


def test_send_container_metrics(
    metric_collection: MetricCollection,
    cluster_collector_client,
) -> None:
    """`container_metrics` endpoint returns all data from queue"""
    response = cluster_collector_client.get(
        "/container_metrics",
        headers={
            "Authorization": "Bearer superdupertoken",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json() == metric_collection.container_metrics


def test_concurrent_update_container_metrics(cluster_collector_client) -> None:
    """`update_container_metrics` endpoint is able to serve concurrent post
    requests"""
    threads = []
    errored_status_codes = []

    def update_metrics():
        response = cluster_collector_client.post(
            "/update_container_metrics",
            headers={
                "Authorization": "Bearer superduperwritertoken",
                "Content-Type": "application/json",
            },
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


def test_concurrent_get_container_metrics(cluster_collector_client) -> None:
    """`container_metrics` endpoint is able to handle concurrent get
    requests"""
    threads = []
    errored_status_codes = []

    def get_metrics():
        response = cluster_collector_client.get(
            "/container_metrics",
            headers={
                "Authorization": "Bearer superdupertoken",
                "Content-Type": "application/json",
            },
        )
        if response.status_code != 200:
            errored_status_codes.append(response.status_code)

    for i in range(100):  # pylint: disable=unused-variable
        threads.append(Thread(target=get_metrics))

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert not errored_status_codes


@pytest.mark.anyio
async def test_authenticate_get_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Service Account with valid token and access to GET endpoints is
    authenticated successfully."""

    def mock_token_review(
        url, headers, data, verify
    ):  # pylint: disable=unused-argument,disallowed-name
        class Response:  # pylint: disable=missing-class-docstring,too-few-public-methods
            def __init__(self):
                self.status_code = 201
                self.content = json.dumps(
                    {
                        "kind": "TokenReview",
                        "apiVersion": "authentication.k8s.io/v1",
                        "metadata": {},
                        "status": {
                            "authenticated": True,
                            "user": {
                                "username": (
                                    "system:serviceaccount:"
                                    "checkmk-monitoring:checkmk-server"
                                ),
                                "uid": "7dbfc985-5b72-41cc-a010-fcfd603af4e5",
                            },
                        },
                    }
                )

        return Response()

    monkeypatch.setattr(requests, "post", mock_token_review)

    assert await authenticate_get(
        HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="superdupertoken",
        ),
        kubernetes_service_host="127.0.0.1",
        kubernetes_service_port_https="6443",
    ) == HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="superdupertoken",
    )


@pytest.mark.anyio
async def test_authenticate_get_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    """Service Account with valid token and no access to GET endpoints is denied
    access."""

    def mock_token_review(
        url, headers, data, verify
    ):  # pylint: disable=unused-argument,disallowed-name
        class Response:  # pylint: disable=missing-class-docstring,too-few-public-methods
            def __init__(self):
                self.status_code = 201
                self.content = json.dumps(
                    {
                        "kind": "TokenReview",
                        "apiVersion": "authentication.k8s.io/v1",
                        "metadata": {},
                        "status": {
                            "authenticated": True,
                            "user": {
                                "username": (
                                    "system:serviceaccount:"
                                    "checkmk-monitoring:node-collector"
                                ),
                                "uid": "7dbfc985-5b72-41cc-a010-fcfd603af4e5",
                            },
                        },
                    }
                )

        return Response()

    monkeypatch.setattr(requests, "post", mock_token_review)

    with pytest.raises(HTTPException) as exception:
        await authenticate_get(
            HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="superdupertoken",
            ),
            kubernetes_service_host="127.0.0.1",
            kubernetes_service_port_https="6443",
        )

    assert exception.type is HTTPException
    assert exception.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert (
        exception.value.detail
        == "Access denied for Service Account node-collector in Namespace checkmk-monitoring."
    )


@pytest.mark.anyio
async def test_authenticate_post_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Service Account with valid token and access to POST endpoints is
    authenticated successfully."""

    def mock_token_review(
        url, headers, data, verify
    ):  # pylint: disable=unused-argument,disallowed-name
        class Response:  # pylint: disable=missing-class-docstring,too-few-public-methods
            def __init__(self):
                self.status_code = 201
                self.content = json.dumps(
                    {
                        "kind": "TokenReview",
                        "apiVersion": "authentication.k8s.io/v1",
                        "metadata": {},
                        "status": {
                            "authenticated": True,
                            "user": {
                                "username": (
                                    "system:serviceaccount:"
                                    "checkmk-monitoring:node-collector"
                                ),
                                "uid": "7dbfc985-5b72-41cc-a010-fcfd603af4e5",
                            },
                        },
                    }
                )

        return Response()

    monkeypatch.setattr(requests, "post", mock_token_review)

    assert await authenticate_post(
        HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="superdupertoken",
        ),
        kubernetes_service_host="127.0.0.1",
        kubernetes_service_port_https="6443",
    ) == HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="superdupertoken",
    )


@pytest.mark.anyio
async def test_authenticate_post_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    """Service Account with valid token and no access to POST endpoints is denied
    access."""

    def mock_token_review(
        url, headers, data, verify
    ):  # pylint: disable=unused-argument,disallowed-name
        class Response:  # pylint: disable=missing-class-docstring,too-few-public-methods
            def __init__(self):
                self.status_code = 201
                self.content = json.dumps(
                    {
                        "kind": "TokenReview",
                        "apiVersion": "authentication.k8s.io/v1",
                        "metadata": {},
                        "status": {
                            "authenticated": True,
                            "user": {
                                "username": (
                                    "system:serviceaccount:"
                                    "checkmk-monitoring:checkmk-server"
                                ),
                                "uid": "7dbfc985-5b72-41cc-a010-fcfd603af4e5",
                            },
                        },
                    }
                )

        return Response()

    monkeypatch.setattr(requests, "post", mock_token_review)

    with pytest.raises(HTTPException) as exception:
        await authenticate_post(
            HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="superdupertoken",
            ),
            kubernetes_service_host="127.0.0.1",
            kubernetes_service_port_https="6443",
        )

    assert exception.type is HTTPException
    assert exception.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert (
        exception.value.detail
        == "Access denied for Service Account checkmk-server in Namespace checkmk-monitoring."
    )


def test_kubernetes_api_host_missing() -> None:
    """Missing Kubernetes API host returns `service unavailable`"""
    with pytest.raises(HTTPException) as exception:
        authenticate(
            HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="superdupertoken",
            ),
            kubernetes_service_host=None,
            kubernetes_service_port_https="6443",
            serviceaccount_whitelist=frozenset({}),
        )

    assert exception.type is HTTPException
    assert exception.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert exception.value.detail == (
        "Unable to verify authentication credentials: cannot read Kubernetes "
        "API hostname and port."
    )


def test_kubernetes_api_port_missing() -> None:
    """Missing Kubernetes API port returns `service unavailable`"""
    with pytest.raises(HTTPException) as exception:
        authenticate(
            HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="superdupertoken",
            ),
            kubernetes_service_host="127.0.0.1",
            kubernetes_service_port_https=None,
            serviceaccount_whitelist=frozenset({}),
        )

    assert exception.type is HTTPException
    assert exception.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert exception.value.detail == (
        "Unable to verify authentication credentials: cannot read Kubernetes "
        "API hostname and port."
    )


def test_authenticate_token_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid Kubernetes `token` is denied access."""

    def mock_token_review(
        url, headers, data, verify
    ):  # pylint: disable=unused-argument,disallowed-name
        class Response:  # pylint: disable=missing-class-docstring,too-few-public-methods
            def __init__(self):
                self.status_code = 201
                self.content = json.dumps(
                    {
                        "kind": "TokenReview",
                        "apiVersion": "authentication.k8s.io/v1",
                        "metadata": {},
                        "status": {
                            "user": {},
                            "error": ["invalid bearer token, Token has expired."],
                        },
                    }
                )

        return Response()

    monkeypatch.setattr(requests, "post", mock_token_review)

    with pytest.raises(HTTPException) as exception:
        authenticate(
            HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="superdupertoken",
            ),
            kubernetes_service_host="127.0.0.1",
            kubernetes_service_port_https="6443",
            serviceaccount_whitelist=frozenset({}),
        )

    assert exception.type is HTTPException
    assert exception.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exception.value.detail == "Invalid authentication credentials"


def test_authenticate_(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bad requests to the Kubernetes Review API are propagated."""
    resp_content = {
        "kind": "Status",
        "apiVersion": "v1",
        "metadata": {},
        "status": "Failure",
        "message": (
            'TokenReview in version "v1" cannot be handled as a '
            "TokenReview: v1.TokenReview.Spec: "
            "v1.TokenReviewSpec.Audiences: []string: decode slice: "
            'expect [ or n, but found ", error found in #10 byte of '
            '...|iences": "checkmk-mo|..., bigger context ...|xxx", '
            '"audiences": "checkmk-monitoring"}}|...'
        ),
        "reason": "BadRequest",
        "code": 400,
    }

    def mock_token_review(
        url, headers, data, verify
    ):  # pylint: disable=unused-argument,disallowed-name
        class Response:  # pylint: disable=missing-class-docstring,too-few-public-methods
            def __init__(self):
                self.status_code = 400
                self.content = json.dumps(resp_content)

        return Response()

    monkeypatch.setattr(requests, "post", mock_token_review)

    with pytest.raises(HTTPException) as exception:
        authenticate(
            HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="superdupertoken",
            ),
            kubernetes_service_host="127.0.0.1",
            kubernetes_service_port_https="6443",
            serviceaccount_whitelist=frozenset({}),
        )

    assert exception.type is HTTPException
    assert exception.value.status_code == status.HTTP_400_BAD_REQUEST
    assert exception.value.detail == resp_content
