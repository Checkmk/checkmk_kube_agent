#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

"""Tests for cluster collector API endpoints."""

import json
from inspect import signature
from threading import Thread
from typing import NoReturn, Optional, Sequence, Union
from unittest.mock import Mock

import pytest
import requests
from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

import checkmk_kube_agent.api
from checkmk_kube_agent.api import (
    StandaloneApplication,
    TokenError,
    _init_app_state,
    _raise_from_token_error,
    app,
    authenticate,
    authenticate_get,
    authenticate_post,
    parse_arguments,
)
from checkmk_kube_agent.type_defs import (
    CheckmkKubeAgentMetadata,
    ClusterCollectorMetadata,
    CollectorType,
    Components,
    ContainerMetric,
    HostName,
    MachineSections,
    MachineSectionsCollection,
    Metadata,
    MetricCollection,
    NodeCollectorMetadata,
    NodeName,
    OsName,
    PlatformMetadata,
    PythonCompiler,
    Response,
    Version,
)


class MockSession(
    requests.Session
):  # pylint: disable=missing-class-docstring,super-init-not-called
    def __init__(self, response: Response = Response(status_code=200, content=b"")):
        self.response = response

    def post(self, *args, **kwargs):  # pylint: disable=unused-argument
        return self.response


class MockLogger:
    # pylint: disable=missing-class-docstring, too-few-public-methods
    def __init__(self):
        self.error_called_with: list[Union[str, bytes]] = []

    def error(self, msg: Union[str, bytes]) -> None:
        """Persists error message instead of causing side effects."""
        self.error_called_with.append(msg)


class MockException(Exception):
    """An exception, to indicate calling a NoReturn function in a test context."""


class MockRaiseFromError:
    # pylint: disable=missing-class-docstring, too-few-public-methods
    called_with: Optional[tuple[bytes, str, TokenError]] = None

    def __call__(
        self,
        token_review_response: bytes,
        token: str,
        token_error: TokenError,
    ) -> NoReturn:
        self.called_with = (token_review_response, token, token_error)
        raise MockException()


@pytest.fixture(name="cluster_collector_metadata")
def fixture_cluster_collector_metadata() -> ClusterCollectorMetadata:
    """Example cluster collector metadata"""
    return ClusterCollectorMetadata(
        node=NodeName("nebukadnezar"),
        host_name=HostName("morpheus"),
        container_platform=PlatformMetadata(
            os_name=OsName("alpine"),
            os_version=Version("3.15"),
            python_version=Version("3.9.9"),
            python_compiler=PythonCompiler("GCC"),
        ),
        checkmk_kube_agent=CheckmkKubeAgentMetadata(
            project_version=Version("1.0.0"),
        ),
    )


@pytest.fixture(name="cluster_collector_client")
def fixture_cluster_collector_client(
    cluster_collector_metadata: ClusterCollectorMetadata,
) -> TestClient:
    """Cluster collector API test client"""
    _init_app_state(
        app,
        cache_maxsize=100,
        cache_ttl=120,
        reader_whitelist=["checkmk-monitoring:checkmk-server"],
        writer_whitelist=["checkmk-monitoring:node-collector"],
        tcp_timeout=(10, 12),
        metadata=cluster_collector_metadata,
    )

    def authenticate_with_empty_token() -> str:
        return ""

    app.dependency_overrides[authenticate_post] = authenticate_with_empty_token
    app.dependency_overrides[authenticate_get] = authenticate_with_empty_token

    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_read_api_token(monkeypatch: pytest.MonkeyPatch):
    """Patch Kubernetes token file read"""

    def mock_read_token():
        return ""

    monkeypatch.setattr(checkmk_kube_agent.api, "read_api_token", mock_read_token)


@pytest.fixture(name="metric_collection")
def fixture_metric_collection(
    cluster_collector_metadata: ClusterCollectorMetadata,
) -> MetricCollection:
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
        metadata=NodeCollectorMetadata(
            **dict(cluster_collector_metadata),
            collector_type=CollectorType.CONTAINER_METRICS,
            components=Components(cadvisor_version=Version("v0.43.0")),
        ),
    )


@pytest.fixture(name="machine_sections_collection")
def fixture_machine_sections_collection(
    cluster_collector_metadata: ClusterCollectorMetadata,
) -> MachineSectionsCollection:
    """Machine sections example"""
    return MachineSectionsCollection(
        sections=MachineSections(
            node_name=NodeName("unittest_node_name"),
            sections="<<<section_name>>>\nsection_data 1",
        ),
        metadata=NodeCollectorMetadata(
            **dict(cluster_collector_metadata),
            collector_type=CollectorType.MACHINE_SECTIONS,
            components=Components(checkmk_agent_version=Version("2.1.0i1")),
        ),
    )


@pytest.fixture(name="argv")
def fixture_argv() -> Sequence[str]:
    """Cluster collector main function arguments"""
    return [
        "--address",
        "127.0.0.2",
        "--port",
        "5",
        "--secure-protocol",
        "--ssl-keyfile",
        "my-ssl-keyfile",
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

    assert args.address == "127.0.0.2"
    assert args.port == 5
    assert args.secure_protocol is True
    assert args.ssl_keyfile == "my-ssl-keyfile"
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
    queue, `container_metrics` endpoint returns all data from queue"""
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

    response = cluster_collector_client.get(
        "/container_metrics",
        headers={
            "Authorization": "Bearer superdupertoken",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json() == metric_collection.container_metrics


def test_concurrent_update_container_metrics(
    cluster_collector_client, metric_collection: MetricCollection
) -> None:
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
            data=metric_collection.json(),
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
async def test_authenticate_get_success(cluster_collector_client) -> None:
    """Service Account with valid token and access to GET endpoints is
    authenticated successfully."""

    response = Response(
        status_code=201,
        content=json.dumps(
            {
                "kind": "TokenReview",
                "apiVersion": "authentication.k8s.io/v1",
                "metadata": {},
                "status": {
                    "authenticated": True,
                    "user": {
                        "username": (
                            "system:serviceaccount:" "checkmk-monitoring:checkmk-server"
                        ),
                        "uid": "7dbfc985-5b72-41cc-a010-fcfd603af4e5",
                    },
                },
            }
        ).encode("utf-8"),
    )

    cluster_collector_client.app.state.tcp_session = MockSession(response)

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
async def test_authenticate_get_denied(cluster_collector_client) -> None:
    """Service Account with valid token and no access to GET endpoints is denied
    access."""

    response = Response(
        status_code=201,
        content=json.dumps(
            {
                "kind": "TokenReview",
                "apiVersion": "authentication.k8s.io/v1",
                "metadata": {},
                "status": {
                    "authenticated": True,
                    "user": {
                        "username": (
                            "system:serviceaccount:" "checkmk-monitoring:node-collector"
                        ),
                        "uid": "7dbfc985-5b72-41cc-a010-fcfd603af4e5",
                    },
                },
            }
        ).encode("utf-8"),
    )

    cluster_collector_client.app.state.tcp_session = MockSession(response)

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
        == "Access denied for Service Account node-collector in Namespace checkmk-monitoring!"
        " See logs for TokenReview."
    )


@pytest.mark.anyio
async def test_authenticate_post_success(cluster_collector_client) -> None:
    """Service Account with valid token and access to POST endpoints is
    authenticated successfully."""

    response = Response(
        status_code=201,
        content=json.dumps(
            {
                "kind": "TokenReview",
                "apiVersion": "authentication.k8s.io/v1",
                "metadata": {},
                "status": {
                    "authenticated": True,
                    "user": {
                        "username": (
                            "system:serviceaccount:" "checkmk-monitoring:node-collector"
                        ),
                        "uid": "7dbfc985-5b72-41cc-a010-fcfd603af4e5",
                    },
                },
            }
        ).encode("utf-8"),
    )

    cluster_collector_client.app.state.tcp_session = MockSession(response)

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
async def test_authenticate_post_denied(cluster_collector_client) -> None:
    """Service Account with valid token and no access to POST endpoints is denied
    access."""

    response = Response(
        status_code=201,
        content=json.dumps(
            {
                "kind": "TokenReview",
                "apiVersion": "authentication.k8s.io/v1",
                "metadata": {},
                "status": {
                    "authenticated": True,
                    "user": {
                        "username": (
                            "system:serviceaccount:" "checkmk-monitoring:checkmk-server"
                        ),
                        "uid": "7dbfc985-5b72-41cc-a010-fcfd603af4e5",
                    },
                },
            }
        ).encode("utf-8"),
    )

    cluster_collector_client.app.state.tcp_session = MockSession(response)

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
        == "Access denied for Service Account checkmk-server in Namespace checkmk-monitoring!"
        " See logs for TokenReview."
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
            session=MockSession(),
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
            session=MockSession(),
            serviceaccount_whitelist=frozenset({}),
        )

    assert exception.type is HTTPException
    assert exception.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert exception.value.detail == (
        "Unable to verify authentication credentials: cannot read Kubernetes "
        "API hostname and port."
    )


@pytest.mark.parametrize(
    "response, expected_message, expected_status_code, expected_exception_type",
    [
        pytest.param(
            Response(
                status_code=201,
                content=json.dumps(
                    {
                        "kind": "TokenReview",
                        "apiVersion": "authentication.k8s.io/v1",
                        "metadata": {},
                        "status": {
                            "user": {},
                            "error": ["invalid bearer token, Token has expired."],
                        },
                    }
                ).encode("utf-8"),
            ),
            "Invalid authentication credentials!",
            status.HTTP_401_UNAUTHORIZED,
            type(None),
            id="Invalid Kubernetes `token` is denied access.",
        ),
        pytest.param(
            Response(
                status_code=201,
                content=json.dumps(
                    {
                        "kind": "TokenReview",
                        "apiVersion": "authentication.k8s.io/v1",
                        "metadata": {},
                        "status": {
                            "authenticated": True,
                            "user": {"username": "unknown"},
                            "error": [],
                        },
                    }
                ).encode("utf-8"),
            ),
            "Username has unexpected format!",
            status.HTTP_501_NOT_IMPLEMENTED,
            ValueError,
            id="A token response, where the username does not match the expected format. "
            "This occurs in Rancher for example.",
        ),
        pytest.param(
            Response(
                status_code=201,
                content=json.dumps(
                    {
                        "status": {
                            "authenticated": True,
                        }
                    }
                ).encode("utf-8"),
            ),
            "No user in token_review_response!",
            status.HTTP_501_NOT_IMPLEMENTED,
            type(None),
            id="A token response, where the user is missing. "
            "It's unclear whether such responses exist in reality.",
        ),
        pytest.param(
            Response(status_code=201, content="ERROR superdupertoken".encode("utf-8")),
            "Error while parsing TokenReview!",
            status.HTTP_501_NOT_IMPLEMENTED,
            json.JSONDecodeError,
            id="A token response, which can't be parsed as json.",
        ),
        pytest.param(
            Response(
                status_code=400,
                content=json.dumps(
                    {
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
                ).encode("utf-8"),
            ),
            "HTTP status code indicates error.",
            status.HTTP_400_BAD_REQUEST,
            type(None),
            id="Bad requests to the Kubernetes Review API are propagated.",
        ),
    ],
)
def test_authenticate_check_token_review(
    response: Response,
    expected_message: str,
    expected_status_code: int,
    expected_exception_type: type,
) -> None:
    """Different, which occur while inspecting the TokenReview returned by Kubernetes."""

    token = "superdupertoken"  # nosec

    raise_from_token_error = MockRaiseFromError()
    with pytest.raises(MockException):
        authenticate(
            HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials=token,
            ),
            kubernetes_service_host="127.0.0.1",
            kubernetes_service_port_https="6443",
            session=MockSession(response),
            serviceaccount_whitelist=frozenset({}),
            raise_from_token_error=raise_from_token_error,
        )

    assert raise_from_token_error.called_with is not None
    used_content, used_token, token_error = raise_from_token_error.called_with
    assert used_content == response.content
    assert used_token == token
    assert token_error.message == expected_message
    assert token_error.status_code == expected_status_code
    assert isinstance(token_error.exception, expected_exception_type)


def test__raise_token_error() -> None:
    """Verifies that TokenReview is logged and that token is stripped from it."""

    token = "superdupertoken"  # nosec
    logger = MockLogger()
    with pytest.raises(HTTPException):
        _raise_from_token_error(
            f"ERROR {token}".encode("utf-8"),
            token,
            TokenError(
                status.HTTP_501_NOT_IMPLEMENTED,
                "Error while parsing TokenReview!",
                MockException(),
            ),
            logger=logger,  # type: ignore
        )

    assert len(logger.error_called_with) == 1
    error_called_with = logger.error_called_with[0]
    assert isinstance(error_called_with, bytes)
    assert "ERROR ".encode("utf-8") in error_called_with
    assert token.encode("utf-8") not in error_called_with


def test_machine_sections(
    cluster_collector_client,
    machine_sections_collection: MachineSectionsCollection,
) -> None:
    """Write data into machine sections queue, then read it again."""

    response = cluster_collector_client.post(
        "/update_machine_sections",
        headers={
            "Authorization": "Bearer superdupertoken",
            "Content-Type": "application/json",
        },
        data=machine_sections_collection.json(),
    )
    assert response.status_code == 200
    assert response.json() is None

    response = cluster_collector_client.get(
        "/machine_sections/",
        headers={
            "Authorization": "Bearer superdupertoken",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json() == [
        {
            "node_name": "unittest_node_name",
            "sections": "<<<section_name>>>\nsection_data 1",
        }
    ]


def test_endpoints_request_authentication() -> None:
    """Hackish test to make sure all endpoints check for authentication token."""
    no_auth = {
        "/health",
        "/",
        "/openapi.json",
        "/docs",
        "/redoc",
        "/docs/oauth2-redirect",
    }
    for route in reversed(app.routes):
        if route.path in no_auth:  # type: ignore
            continue
        parameters = signature(route.endpoint).parameters  # type: ignore
        if "token" not in parameters:
            raise Exception(
                f"Expected a token parameter for path '{route.path}'. "  # type:ignore
                "Please add auth!"
            )
        parameter_token = parameters["token"]
        assert str(parameter_token.default) in {
            "Depends(authenticate_get)",
            "Depends(authenticate_post)",
        }


def test_standalone_application() -> None:
    """some basic tests for setting up the gunicorn app"""
    app_ = Mock()

    StandaloneApplication.cfg = Mock()
    standalone = StandaloneApplication(app_, {"bind": "value:8080"})
    standalone.load_config()
    assert standalone.load() is app_
    assert standalone.cfg.bind == ["value:8080"]


def test_send_metadata(
    cluster_collector_metadata: ClusterCollectorMetadata,
    metric_collection: MetricCollection,
    machine_sections_collection: MachineSectionsCollection,
    cluster_collector_client: TestClient,
) -> None:
    """`metadata` endpoint returns cluster and node collector metadata"""

    response = cluster_collector_client.post(
        "/update_container_metrics",
        headers={
            "Authorization": "Bearer superduperwritertoken",
        },
        json=jsonable_encoder(metric_collection),
    )
    assert response.status_code == 200

    response = cluster_collector_client.post(
        "/update_machine_sections",
        headers={
            "Authorization": "Bearer superduperwritertoken",
        },
        json=jsonable_encoder(machine_sections_collection),
    )
    assert response.status_code == 200

    response = cluster_collector_client.get(
        "/metadata",
        headers={
            "Authorization": "Bearer superdupertoken",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json() == Metadata(
        cluster_collector_metadata=cluster_collector_metadata,
        node_collector_metadata=[
            metric_collection.metadata,
            machine_sections_collection.metadata,
        ],
    )
