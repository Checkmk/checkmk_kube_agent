#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2022 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

# pylint: disable=missing-function-docstring, missing-class-docstring, no-self-use, too-few-public-methods

"""Integration tests for collectors"""
from __future__ import annotations

import json
import re
import subprocess  # nosec
import time
from pathlib import Path
from typing import Any, Iterable, NamedTuple, Sequence, Tuple

import pytest
import requests
import urllib3

from tests.integration import kube_api_helpers
from tests.integration.common_helpers import tcp_session

# pylint: disable=fixme
from tests.integration.helm_chart_helpers import (
    CollectorImages,
    DeployableNamespace,
    HelmChartDeploymentSettings,
    NodePort,
    apply_collector_helm_chart,
    uninstall_collector_helm_chart,
)
from tests.integration.kube_api_helpers import NodeType


class SetupError(Exception):
    """Custom error to indicate a setup error"""


class CollectorDetails(NamedTuple):
    """NamedTuple which contains the cluster collector connection details"""

    endpoint: str
    token: str


class Ingress(NamedTuple):
    name: str
    chart_settings: Sequence[str]


class TestDefaultCollectors:
    @pytest.fixture(scope="class", params=["NodePort"])
    # TODO: change typing to pytest.FixtureRequest once it's been added:
    # https://github.com/pytest-dev/pytest/issues/8073
    def external_access_method(self, request: Any) -> NodePort:
        """Method with which the cluster collector is accessible from outside the
        Kubernetes cluster.

        Note:
            Not all options provided by Kubernetes are supported. The supported
            options are dictated by the options exposed in the helm chart.

        See also:
            https://kubernetes.io/docs/concepts/services-networking/
        """

        if request.param == "NodePort":
            return NodePort(
                name="NodePort",
                chart_settings=[
                    "clusterCollector.service.type=NodePort",
                    "clusterCollector.service.nodePort=30035",
                ],
            )
        # TODO: implement ingress
        raise SystemExit(f"Unknown external access method: {request.param}")

    @pytest.fixture(scope="class")
    def deployment_settings(
        self,
        helm_chart_path: Path,
        collector_images: CollectorImages,
        external_access_method: NodePort,
    ) -> HelmChartDeploymentSettings:
        return HelmChartDeploymentSettings(
            path=helm_chart_path,
            release_name="checkmk",
            release_namespace=DeployableNamespace("checkmk-monitoring"),
            images=collector_images,
            external_access_method=external_access_method,
            additional_chart_settings=[],
        )

    @pytest.fixture(scope="class")
    def collector(
        self,
        api_server: kube_api_helpers.APIServer,
        worker_nodes_count: int,
        deployment_settings: HelmChartDeploymentSettings,
    ) -> Iterable[CollectorDetails]:
        """Fixture to deploy and clean up collectors"""
        deploy_output = apply_collector_helm_chart(deployment_settings)
        collector_details = _parse_collector_connection_details(
            command_resp=deploy_output,
            collector_namespace=deployment_settings.release_namespace,
            release_name=deployment_settings.release_name,
        )

        token = collector_details.token
        kube_api_helpers.wait_for_daemonset_pods(
            api_client=api_server,
            namespace=deployment_settings.release_namespace,
            name="checkmk-node-collector-machine-sections",
            observing_state="numberReady",
        )
        kube_api_helpers.wait_for_deployment(
            api_client=api_server,
            namespace=deployment_settings.release_namespace,
            name="checkmk-cluster-collector",
        )
        session = tcp_session(
            headers={"Authorization": f"Bearer {token}"}, backoff_factor=5.0
        )
        _wait_for_cluster_collector_available(
            cluster_endpoint=collector_details.endpoint,
            session=session,
        )
        _wait_for_node_collectors_to_send_metrics(
            session=session,
            cluster_endpoint=collector_details.endpoint,
            worker_nodes_count=worker_nodes_count,
        )
        yield collector_details
        uninstall_collector_helm_chart(deployment_settings)

    @pytest.mark.timeout(400)
    def test_authentication_cluster_collector_with_invalid_token(
        self,
        collector: CollectorDetails,
    ) -> None:
        session = tcp_session(headers={"Authorization": "Bearer invalid_token"})

        response_collector = session.get(f"{collector.endpoint}/metadata")
        assert response_collector.status_code == 401
        assert response_collector.json()["detail"].startswith(
            "Invalid authentication credentials"
        )

    @pytest.mark.timeout(400)
    def test_authentication_cluster_collector_with_no_token(
        self, collector: CollectorDetails
    ) -> None:
        session = tcp_session()

        response_collector = session.get(f"{collector.endpoint}/metadata")
        assert response_collector.status_code == 403

    @pytest.mark.timeout(400)
    def test_authentication_cluster_collector_with_non_whitelisted_token(
        self, cluster_token: str, collector: CollectorDetails
    ) -> None:
        session = tcp_session(headers={"Authorization": f"Bearer {cluster_token}"})

        response_collector = session.get(f"{collector.endpoint}/metadata")
        assert response_collector.status_code == 401
        assert response_collector.json()["detail"].startswith(
            "Access denied for Service Account"
        )

    @pytest.mark.timeout(400)
    @pytest.mark.usefixtures("collector")
    def test_cluster_collector_has_resources(
        self,
        api_server: kube_api_helpers.APIServer,
        deployment_settings: HelmChartDeploymentSettings,
    ) -> None:
        deployment_name = "checkmk-cluster-collector"
        api_response = api_server.get(
            f"/apis/apps/v1/namespaces/{deployment_settings.release_namespace}"
            f"/deployments/{deployment_name}"
        )
        cluster_collector_deployment = json.loads(api_response.response)
        containers = cluster_collector_deployment["spec"]["template"]["spec"][
            "containers"
        ]
        resources = containers[0]["resources"]

        assert len(containers) == 1
        assert "cpu" in resources["requests"]
        assert "memory" in resources["requests"]
        assert "cpu" in resources["limits"]
        assert "memory" in resources["limits"]

    @pytest.mark.timeout(400)
    @pytest.mark.usefixtures("collector")
    @pytest.mark.parametrize(
        "daemonset_component", [("container-metrics", 2), ("machine-sections", 1)]
    )
    def test_node_collector_has_resources(
        self,
        daemonset_component: Tuple[str, int],
        api_server: kube_api_helpers.APIServer,
        deployment_settings: HelmChartDeploymentSettings,
    ) -> None:
        daemonset_section_name, containers_count = daemonset_component
        daemonset_name = f"checkmk-node-collector-{daemonset_section_name}"
        api_response = api_server.get(
            f"/apis/apps/v1/namespaces/{deployment_settings.release_namespace}"
            f"/daemonsets/{daemonset_name}"
        )
        node_collector_daemonset = json.loads(api_response.response)
        containers = node_collector_daemonset["spec"]["template"]["spec"]["containers"]

        assert len(containers) == containers_count
        assert all(
            "cpu" in container["resources"]["requests"] for container in containers
        )
        assert all(
            "memory" in container["resources"]["requests"] for container in containers
        )
        assert all(
            "cpu" in container["resources"]["limits"] for container in containers
        )
        assert all(
            "memory" in container["resources"]["limits"] for container in containers
        )

    @pytest.mark.timeout(400)
    def test_each_node_generates_machine_sections(
        self,
        api_server: kube_api_helpers.APIServer,
        collector: CollectorDetails,
    ) -> None:
        session = tcp_session(headers={"Authorization": f"Bearer {collector.token}"})

        machine_sections = session.get(f"{collector.endpoint}/machine_sections").json()

        assert machine_sections
        assert {
            node.name
            for node in kube_api_helpers.request_nodes(api_server)
            if node.role == NodeType.WORKER
        } == {section["node_name"] for section in machine_sections}

    @pytest.mark.timeout(400)
    def test_container_metrics(
        self,
        collector: CollectorDetails,
    ) -> None:
        session = tcp_session(headers={"Authorization": f"Bearer {collector.token}"})

        container_metrics = session.get(
            f"{collector.endpoint}/container_metrics"
        ).json()

        assert container_metrics


def _wait_for_cluster_collector_available(
    cluster_endpoint: str, session: requests.Session
) -> None:
    """Wait for cluster collector to be available"""

    def cluster_collector_available():
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        resp = session.get(f"{cluster_endpoint}/metadata", verify=False)
        return resp.status_code == 200

    while not cluster_collector_available():
        time.sleep(1)


def _wait_for_node_collectors_to_send_metrics(
    session: requests.Session, cluster_endpoint: str, worker_nodes_count: int
) -> None:
    """Wait for all node collectors to send first metrics"""

    def all_node_collectors_sent_metrics():
        resp = session.get(f"{cluster_endpoint}/metadata", verify=False)
        if resp.status_code != 200:
            return False
        metadata = resp.json()
        return (
            len(metadata["node_collector_metadata"]) == worker_nodes_count * 2
        )  # 2 for container & machine sections

    while not all_node_collectors_sent_metrics():
        time.sleep(1)


def _parse_collector_connection_details(
    command_resp: str, collector_namespace: str, release_name: str
) -> CollectorDetails:
    """Parse the collector connection details from helm chart response"""
    connection_details = {}
    for instruction in command_resp.split("\n"):
        if not (command := instruction.strip()).startswith("export"):
            continue

        if all(
            component not in command for component in ("CA_CRT", "NODE_PORT", "NODE_IP")
        ):
            continue

        setup_element = re.findall(r"export (.*?)\=", command)[0]
        if re.search(r"\((.*?)\);", command):
            setup_command = re.findall(r"\((.*?)\);", command)[0]
        else:
            setup_command = re.findall(r"\((.*?)\)\";", command)[0]

        setup_process = subprocess.run(
            setup_command, shell=True, check=True, capture_output=True  # nosec
        )
        connection_details[setup_element.lower()] = setup_process.stdout.decode("utf-8")

    token_command = subprocess.run(  # nosec
        f"kubectl create token --duration=0s -n {collector_namespace} {release_name}-checkmk",
        shell=True,
        check=True,
        capture_output=True,
    )
    connection_details["token"] = token_command.stdout.decode("utf-8")
    if any(key not in connection_details for key in ("node_ip", "node_port", "token")):
        raise SetupError("Helm chart output did not contain all connection details")

    return CollectorDetails(
        endpoint=f"http://{connection_details['node_ip']}:{connection_details['node_port']}",
        token=connection_details["token"],
    )
