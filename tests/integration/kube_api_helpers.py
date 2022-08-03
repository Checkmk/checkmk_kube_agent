#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2022 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

"""Helper functions to help communicate with the API server of a running Kubernetes cluster"""
import enum
import json
import time
from dataclasses import dataclass
from typing import Final, NamedTuple, Sequence

import requests

# pylint: disable=fixme


class KubernetesError(Exception):
    """Custom error to indicate a Kubernetes related error"""


@dataclass
class APIResponse:
    """Class containing the details of the Kubernetes API server response"""

    response: str
    status_code: int
    headers: dict


class DeployedPod(NamedTuple):
    """Basic details of a deployed pod"""

    name: str
    namespace: str


class NodeType(enum.Enum):
    """Node type"""

    WORKER = "worker"
    MASTER = "master"


class Node(NamedTuple):
    """Minimum node information from the Kubernetes API"""

    name: str
    role: NodeType


class APIServer:
    """Class to facilitate communication to the Kubernetes API server"""

    # pylint: disable=too-few-public-methods
    def __init__(self, session: requests.Session, cluster_endpoint: str) -> None:
        self.session: Final = session
        self.cluster_endpoint: Final = cluster_endpoint

    def get(self, resource_path: str) -> APIResponse:
        """Perform a get resource request against the API server"""
        response = self.session.get(
            f"{self.cluster_endpoint}{resource_path}", verify=False
        )
        return APIResponse(
            response=response.text,
            status_code=response.status_code,
            headers=dict(response.headers),
        )


def request_nodes(api_server: APIServer) -> Sequence[Node]:
    """Request the nodes from the Kubernetes cluster"""
    return _parse_nodes(json.loads(api_server.get("/api/v1/nodes").response)["items"])


def _parse_nodes(raw_nodes: Sequence[dict]) -> Sequence[Node]:
    """Parse the raw API response nodes"""

    def _parse_node_roles(labels: Sequence[str]) -> Sequence[str]:
        if labels is None:
            return []
        return [
            role
            for label in labels
            if (
                role := label[len("node-role.kubernetes.io/") :]
                if label.startswith("node-role.kubernetes.io/")
                else None
            )
            is not None
        ]

    nodes = []
    for node in raw_nodes:
        roles = _parse_node_roles(node["metadata"]["labels"])
        nodes.append(
            Node(
                name=node["metadata"]["name"],
                role=NodeType.MASTER
                if ("master" in roles or "control_plane" in roles)
                else NodeType.WORKER,
            )
        )
    return nodes


def wait_for_daemonset_pods(api_client: APIServer, namespace: str, name: str):
    """Waiting for daemonset daemon pods to enter ready state"""

    def daemonset_is_ready():
        api_resp = api_client.get(
            f"/apis/apps/v1/namespaces/{namespace}/daemonsets/{name}"
        )
        details = json.loads(api_resp.response)
        try:
            desired_nodes = details["status"]["desiredNumberScheduled"]
            ready_nodes = details["status"]["numberReady"]
        except (KeyError, TypeError):
            # the API response can be sometimes None
            return False

        if ready_nodes > desired_nodes:
            raise KubernetesError(
                f"Daemonset {name} has more higher numberReady value than desiredNumberScheduled"
            )
        return ready_nodes == desired_nodes

    while not daemonset_is_ready():
        time.sleep(1)


def wait_for_deployment(api_client: APIServer, namespace: str, name: str):
    """Wait for at least one deployment replica to be ready"""

    def deployment_minimum_one_replica_ready():
        api_resp = api_client.get(
            f"/apis/apps/v1/namespaces/{namespace}/deployments/{name}"
        )
        details = json.loads(api_resp.response)
        try:
            return details["status"]["readyReplicas"] > 0
        except (KeyError, TypeError):
            # the API response can be sometimes None
            return False

    while not deployment_minimum_one_replica_ready():
        time.sleep(1)
