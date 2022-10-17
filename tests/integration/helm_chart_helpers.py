#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2022 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

# pylint: disable=missing-function-docstring, missing-class-docstring, no-self-use, too-few-public-methods
"""Helper functions to help apply the Checkmk Kubernetes monitoring helm chart"""
from __future__ import annotations

import itertools
import json
import subprocess  # nosec
from pathlib import Path
from typing import NamedTuple, Optional, Sequence

# pylint: disable=fixme


class NodePort(NamedTuple):
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


def apply_collector_helm_chart(
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


def uninstall_collector_helm_chart(
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
