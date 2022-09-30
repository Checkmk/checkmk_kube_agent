#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2022 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

"""Conftest file for integration tests"""

import pytest
from _pytest.config.argparsing import Parser

from tests.integration.common_helpers import tcp_session
from tests.integration.kube_api_helpers import APIServer


def pytest_addoption(
    parser: Parser,
) -> None:
    # pylint: disable=missing-function-docstring
    parser.addoption(
        "--cluster-endpoint",
        action="store",
        help="The endpoint to access the Kubernetes cluster",
    )
    parser.addoption(
        "--cluster-token",
        action="store",
        help="The service account token to get access to the Kubernetes API",
    )
    parser.addoption(
        "--cluster-workers", action="store", help="The number of Kubernetes workers"
    )
    parser.addoption(
        "--helm-chart-path",
        action="store",
        help="The name of the checkmk_kube_agent chart",
        default="deploy/charts/checkmk",
    )


@pytest.fixture(scope="session", name="worker_nodes_count")
def fixture_worker_nodes_count(request: pytest.FixtureRequest) -> int:
    """Fixture for the count of worker nodes"""
    return int(request.config.getoption("cluster_workers"))


@pytest.fixture(scope="session", name="cluster_endpoint")
def fixture_cluster_endpoint(request: pytest.FixtureRequest) -> str:
    """Fixture for cluster endpoint"""
    return request.config.getoption("cluster_endpoint")


@pytest.fixture(scope="session", name="cluster_token")
def fixture_cluster_token(request: pytest.FixtureRequest) -> str:
    """Fixture for cluster token"""
    return request.config.getoption("cluster_token")


@pytest.fixture(scope="session", name="helm_chart_path")
def fixture_helm_chart_path(request: pytest.FixtureRequest) -> str:
    """Fixture for helm chart path"""
    return request.config.getoption("helm_chart_path")


@pytest.fixture(scope="class", name="api_server")
def fixture_api_server(cluster_endpoint: str, cluster_token: str) -> APIServer:
    """Fixture for API server class"""
    return APIServer(
        session=tcp_session(headers={"authorization": f"Bearer {cluster_token}"}),
        cluster_endpoint=cluster_endpoint,
    )
