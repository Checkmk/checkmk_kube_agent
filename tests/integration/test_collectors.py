#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2022 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

# pylint: disable=missing-function-docstring, missing-class-docstring, no-self-use, too-few-public-methods

"""Integration tests for collectors"""
import re
import subprocess  # nosec
import time
from typing import NamedTuple

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


@pytest.fixture(scope="session", name="helm_chart_name")
def fixture_release_chart(request) -> str:
    """Fixture for release chart name"""
    return request.config.getoption("helm_chart_name")


@pytest.fixture(scope="class", name="collector")
def fixture_collector(
    helm_chart_path: str,
    api_server: kube_api_helpers.APIServer,
    worker_nodes_count: int,
):
    """Fixture to deploy and clean up collectors"""
    # TODO: parametrize collector namespace
    collector_namespace = "default"
    release_name = "checkmk"
    deploy_output = _apply_collector_helm_chart(
        release_namespace=collector_namespace,
        chart_path=helm_chart_path,
        release_name=release_name,
    )
    collector_details = _parse_collector_connection_details(
        command_resp=deploy_output,
        collector_namespace=collector_namespace,
        release_name=release_name,
    )

    token = collector_details.token
    kube_api_helpers.wait_for_daemonset_pods(
        api_client=api_server,
        namespace=collector_namespace,
        name="checkmk-node-collector-machine-sections",
    )
    kube_api_helpers.wait_for_deployment(
        api_client=api_server,
        namespace=collector_namespace,
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
    helm_delete_command = (
        f"helm uninstall -n {collector_namespace} {release_name}".split(" ")
    )
    subprocess.run(  # nosec
        helm_delete_command,
        shell=False,
        check=True,
    )


class TestCollectors:
    @pytest.mark.timeout(60)
    def test_each_node_generates_machine_sections(
        self,
        api_server: kube_api_helpers.APIServer,
        collector: CollectorDetails,
    ):
        session = tcp_session(headers={"Authorization": f"Bearer {collector.token}"})

        machine_sections = session.get(f"{collector.endpoint}/machine_sections").json()

        assert machine_sections
        assert {
            node.name
            for node in kube_api_helpers.request_nodes(api_server)
            if node.role == NodeType.WORKER
        } == {section["node_name"] for section in machine_sections}


def _apply_collector_helm_chart(
    release_name: str,
    chart_path: str,
    release_namespace: str = "checkmk",
    port: int = 30035,
) -> str:
    """Perform helm install command to deploy monitoring collectors

    the helm chart must be install using the NodePort option
    """
    # TODO: read the kubectl get secret from config file (yaml file)
    helm_install_command = (
        f"helm upgrade --install --create-namespace -n {release_namespace} "
        f"{release_name} {chart_path} --set clusterCollector.service.type=NodePort "
        f"--set clusterCollector.service.nodePort={port}".split(" ")
    )

    process = subprocess.run(  # nosec
        helm_install_command,
        shell=False,
        check=True,
        capture_output=True,
    )
    return process.stdout.decode("utf-8")


def _wait_for_cluster_collector_available(
    cluster_endpoint: str, session: requests.Session
):
    """Wait for cluster collector to be available"""

    def cluster_collector_available():
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        resp = session.get(f"{cluster_endpoint}/metadata", verify=False)
        return resp.status_code == 200

    while not cluster_collector_available():
        time.sleep(1)


def _wait_for_node_collectors_to_send_metrics(
    session: requests.Session, cluster_endpoint: str, worker_nodes_count: int
):
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
