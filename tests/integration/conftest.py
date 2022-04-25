#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

"""Connection parameters for integration tests."""

import configparser

import pytest

CONFIG = configparser.ConfigParser()
for config_file in ["kubernetes-master.ini", "kubernetes-nodes.ini"]:
    CONFIG.read(config_file)


@pytest.fixture(scope="session")
def kubernetes_master():
    """Kubernetes master node"""
    return CONFIG["kubernetes-master"]["master_node"]


@pytest.fixture(scope="session")
def api_server_endpoint_https(kubernetes_master):
    """Kubernetes API server HTTPS endpoint URL"""
    return f"https://{kubernetes_master}:6443"


@pytest.fixture(scope="session")
def api_server_endpoint_http(kubernetes_master):
    """Kubernetes API server HTTP endpoint URL"""
    return f"http://{kubernetes_master}:443"


@pytest.fixture(scope="session")
def token():
    """Kubernetes Token of the checkmk user"""
    return CONFIG["kubernetes-master"]["token"]


@pytest.fixture(scope="session")
def kubernetes_worker_nodes():
    """Kubernetes worker nodes"""
    nodes = list(CONFIG["kubernetes-worker"].values())
    if len(nodes) == 0:
        raise AssertionError("No worker nodes found for kubernetes cluster")
    return nodes


@pytest.fixture(scope="session")
def cluster_collector_endpoint_https(kubernetes_worker_nodes):
    """Cluster collector API HTTPS endpoint URL

    Any random worker node can be used to connect with cluster collector, as
    the relevant NodePort is available on all worker nodes."""
    return f"https://{kubernetes_worker_nodes[0]}:30035"


@pytest.fixture(scope="session")
def cluster_collector_endpoint_http(kubernetes_worker_nodes):
    """Cluster collector API HTTP endpoint URL

    Any random worker node can be used to connect with cluster collector, as
    the relevant NodePort is available on all worker nodes."""
    return f"http://{kubernetes_worker_nodes[0]}:30035"
