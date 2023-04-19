#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2022 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

# pylint: disable=missing-function-docstring, missing-class-docstring, no-self-use, too-few-public-methods

"""Integration tests for collectors"""
from __future__ import annotations

import itertools
import json
import re
import subprocess  # nosec
import time
from pathlib import Path
from typing import Any, Iterable, NamedTuple, Optional, Sequence

import pytest
import requests
import urllib3

from tests.integration import kube_api_helpers
from tests.integration.common_helpers import tcp_session

# pylint: disable=fixme
from tests.integration.kube_api_helpers import NodeType


class SetupError(Exception):
    """Custom error to indicate a setup error"""


class CollectorDetails(NamedTuple):
    """NamedTuple which contains the cluster collector connection details"""

    endpoint: str
    token: str


class NodePort(NamedTuple):
    name: str
    chart_settings: Sequence[str]


class Ingress(NamedTuple):
    name: str
    chart_settings: Sequence[str]


class CollectorImages(NamedTuple):
    tag: Optional[str]
    pull_secret: Optional[str]
    cluster_collector: str
    node_collector_cadvisor: str
    node_collector_machine_sections: str
    node_collector_container_metrics: str

    def chart_settings(self) -> Sequence[str]:
        settings = [
            f"clusterCollector.image.repository={self.cluster_collector}",
            f"nodeCollector.cadvisor.image.repository={self.node_collector_cadvisor}",
            (
                "nodeCollector.containerMetricsCollector.image.repository="
                f"{self.node_collector_container_metrics}"
            ),
            (
                "nodeCollector.machineSectionsCollector.image.repository="
                f"{self.node_collector_machine_sections}"
            ),
        ]

        if self.tag:
            settings.append(f"image.tag={self.tag}")

        if self.pull_secret:
            settings.append(f"imagePullSecrets[0].name={self.pull_secret}")

        return settings


class CollectorConfiguration(NamedTuple):
    """Collector configuration options as provided by the helm chart."""

    # TODO: implement more of these settings: CMK-10834
    images: CollectorImages
    external_access_method: NodePort


class DeployableNamespace(str):
    """System-owned or default namespaces are not deployable."""

    def __new__(cls, namespace: str) -> DeployableNamespace:
        if namespace in (
            "",
            "default",
            "kube-flannel",
            "kube-node-lease",
            "kube-public",
            "kube-system",
        ):
            raise ValueError(f"You may not deploy to namespace '{namespace}'")
        return super().__new__(cls, namespace)


class HelmChartDeploymentSettings(NamedTuple):
    """Helm chart settings available for deployment of the objects to the
    Kubernetes cluster."""

    path: Path
    release_name: str
    release_namespace: DeployableNamespace
    collector_configuration: CollectorConfiguration

    def install_command(self) -> Sequence[str]:
        additional_settings = list(
            itertools.chain.from_iterable(
                ("--set", s)
                for s in [
                    *self.collector_configuration.external_access_method.chart_settings,
                    *self.collector_configuration.images.chart_settings(),
                ]
            )
        )

        return [
            "helm",
            "upgrade",
            "--install",
            "--create-namespace",
            "-n",
            self.release_namespace,
            self.release_name,
            str(self.path),
        ] + additional_settings

    def uninstall_command(self) -> Sequence[str]:
        return [
            "helm",
            "uninstall",
            "-n",
            self.release_namespace,
            self.release_name,
        ]


class TestCollectors:
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
        image_registry: str,
        image_pull_secret_name: Optional[str],
        collector_image_name: str,
        cadvisor_image_name: str,
        image_tag: str,
        external_access_method: NodePort,
    ) -> HelmChartDeploymentSettings:
        # pylint: disable=too-many-arguments
        collector_image = f"{image_registry}/{collector_image_name}"
        return HelmChartDeploymentSettings(
            path=Path("deploy/charts/checkmk"),
            release_name="checkmk",
            release_namespace=DeployableNamespace("checkmk-monitoring"),
            collector_configuration=CollectorConfiguration(
                images=CollectorImages(
                    tag=image_tag,
                    pull_secret=image_pull_secret_name,
                    cluster_collector=collector_image,
                    node_collector_machine_sections=collector_image,
                    node_collector_container_metrics=collector_image,
                    node_collector_cadvisor=f"{image_registry}/{cadvisor_image_name}",
                ),
                external_access_method=external_access_method,
            ),
        )

    @pytest.fixture(scope="class")
    def collector(
        self,
        api_server: kube_api_helpers.APIServer,
        worker_nodes_count: int,
        deployment_settings: HelmChartDeploymentSettings,
    ) -> Iterable[CollectorDetails]:
        """Fixture to deploy and clean up collectors"""
        deploy_output = _apply_collector_helm_chart(deployment_settings)
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
        _uninstall_collector_helm_chart(deployment_settings)

    @pytest.mark.timeout(60)
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

    @pytest.mark.timeout(60)
    def test_container_metrics(
        self,
        collector: CollectorDetails,
    ) -> None:
        session = tcp_session(headers={"Authorization": f"Bearer {collector.token}"})

        container_metrics = session.get(
            f"{collector.endpoint}/container_metrics"
        ).json()

        assert container_metrics


def _apply_collector_helm_chart(
    deployment_settings: HelmChartDeploymentSettings,
) -> str:
    """Perform helm install command to deploy monitoring collectors

    the helm chart must be install using the NodePort option
    """
    subprocess.run(  # nosec
        [
            "kubectl",
            "create",
            "namespace",
            deployment_settings.release_namespace,
        ],
        shell=False,
        check=True,
    )
    _copy_pull_secret_to_namespace(
        deployment_settings.release_namespace,
        deployment_settings.collector_configuration.images.pull_secret,
    )
    process = subprocess.run(  # nosec
        deployment_settings.install_command(),
        shell=False,
        check=True,
        capture_output=True,
    )
    return process.stdout.decode("utf-8")


def _copy_pull_secret_to_namespace(namespace: str, secret: Optional[str]) -> None:
    """Copy the pull secret which is needed to retrieve images from a private
    registry to the namespace where the collectors should be deployed.

    Note:
        A pod cannot access a pull secret that lives in a different namespace.

    See also:
        https://kubernetes.io/docs/concepts/configuration/secret/#details
    """
    if not secret:
        return

    secret_config = json.loads(
        subprocess.run(  # nosec
            [
                "kubectl",
                "get",
                "secret",
                secret,
                "--namespace=default",
                "-o",
                "json",
            ],
            shell=False,
            check=True,
            capture_output=True,
        ).stdout
    )
    secret_config["metadata"]["namespace"] = namespace
    subprocess.run(  # nosec
        ["kubectl", "create", "-f", "-"],
        input=json.dumps(secret_config).encode("utf-8"),
        shell=False,
        check=True,
    )


def _uninstall_collector_helm_chart(
    deployment_settings: HelmChartDeploymentSettings,
) -> None:
    subprocess.run(  # nosec
        deployment_settings.uninstall_command(),
        shell=False,
        check=True,
    )
    subprocess.run(  # nosec
        [
            "kubectl",
            "delete",
            "namespace",
            deployment_settings.release_namespace,
        ],
        shell=False,
        check=True,
    )


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
