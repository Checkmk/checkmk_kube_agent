#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2022 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

# pylint: disable=missing-function-docstring, missing-class-docstring, no-self-use, too-few-public-methods

"""Integration tests for helm chart"""
from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

# pylint: disable=fixme
from tests.integration import kube_api_helpers
from tests.integration.helm_chart_helpers import (
    CollectorImages,
    DeployableNamespace,
    HelmChartDeploymentSettings,
    apply_collector_helm_chart,
    node_port_chart_settings,
    security_context_run_as_non_root_settings,
    security_context_run_as_user_settings,
    uninstall_collector_helm_chart,
)

CLUSTER_COLLECTOR_DEPLOYMENT_NAME: Final = "checkmk-cluster-collector"
NODE_COLLECTOR_DAEMONSET_NAME: Final = "checkmk-node-collector"


class TestSecurityContexts:
    @pytest.fixture(scope="class")
    def deployment_settings(
        self,
        helm_chart_path: Path,
        collector_images: CollectorImages,
    ) -> HelmChartDeploymentSettings:
        return HelmChartDeploymentSettings(
            path=helm_chart_path,
            release_name="checkmk",  # TODO: must be changed once secret copy works
            release_namespace=DeployableNamespace("checkmk-monitoring"),
            images=collector_images,
            external_access_method=node_port_chart_settings(),
            additional_chart_settings=[
                security_context_run_as_user_settings(run_as_user=0),
                security_context_run_as_non_root_settings(run_as_non_root=True),
            ],
        )

    @pytest.fixture(scope="class")
    def collector(
        self,
        api_server: kube_api_helpers.APIServer,
        deployment_settings: HelmChartDeploymentSettings,
    ):
        apply_collector_helm_chart(deployment_settings)
        kube_api_helpers.wait_for_daemonset_pods(
            api_client=api_server,
            namespace=deployment_settings.release_namespace,
            name=f"{NODE_COLLECTOR_DAEMONSET_NAME}-machine-sections",
            observing_state="currentNumberScheduled",
        )
        kube_api_helpers.wait_for_daemonset_pods(
            api_client=api_server,
            namespace=deployment_settings.release_namespace,
            name=f"{NODE_COLLECTOR_DAEMONSET_NAME}-container-metrics",
            observing_state="currentNumberScheduled",
        )
        kube_api_helpers.wait_for_collector_pod_containers_to_exit_creation_state(
            api_client=api_server,
            collectors_pod_names=[
                f"{CLUSTER_COLLECTOR_DEPLOYMENT_NAME}",
                f"{NODE_COLLECTOR_DAEMONSET_NAME}-machine-sections",
                f"{NODE_COLLECTOR_DAEMONSET_NAME}-container-metrics",
            ],
            namespace=deployment_settings.release_namespace,
        )
        yield
        uninstall_collector_helm_chart(deployment_settings)

    @pytest.mark.usefixtures("collector")
    @pytest.mark.timeout(120)
    def test_node_collector_machine_sections_root_security_context(
        self,
        api_server: kube_api_helpers.APIServer,
        deployment_settings: HelmChartDeploymentSettings,
        worker_nodes_count: int,
    ):
        pods = kube_api_helpers.get_pods_from_namespace(
            api_client=api_server, namespace=deployment_settings.release_namespace
        )
        node_collector_pods = [
            pod
            for pod in pods
            if any(
                pod["metadata"]["name"].startswith(collector_name)
                for collector_name in (
                    f"{NODE_COLLECTOR_DAEMONSET_NAME}-machine-sections",
                    f"{NODE_COLLECTOR_DAEMONSET_NAME}-container-metrics",
                )
            )
        ]

        assert len(node_collector_pods) == worker_nodes_count * 2
        assert all(
            (
                "breaks non-root policy"
                in pod["status"]["containerStatuses"][0]["state"]["waiting"]["message"]
                for pod in node_collector_pods
            )
        )

    @pytest.mark.usefixtures("collector")
    @pytest.mark.timeout(120)
    def test_cluster_collector_root_security_context(
        self,
        api_server: kube_api_helpers.APIServer,
        deployment_settings: HelmChartDeploymentSettings,
    ):
        pods = kube_api_helpers.get_pods_from_namespace(
            api_client=api_server, namespace=deployment_settings.release_namespace
        )
        cluster_collector_pods = [
            pod
            for pod in pods
            if pod["metadata"]["name"].startswith(
                f"{CLUSTER_COLLECTOR_DEPLOYMENT_NAME}"
            )
        ]

        assert len(cluster_collector_pods) == 1
        assert all(
            (
                "breaks non-root policy"
                in pod["status"]["containerStatuses"][0]["state"]["waiting"]["message"]
                for pod in cluster_collector_pods
            )
        )
