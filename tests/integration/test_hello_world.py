#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

"""Connection parameters for integration tests."""

import json
import requests


def test_cluster_collector_connection(cluster_collector_endpoint_http):
    resp = requests.get(f"{cluster_collector_endpoint_http}/health")

    assert resp.status_code == 200
    assert json.loads(resp.content) == {"status": "available"}


def test_kubernetes_api_connection(api_server_endpoint_https, token):
    resp = requests.get(
        f"{api_server_endpoint_https}/api/v1/nodes",
        headers={"Authorization": f"Bearer {token}"},
        verify=False,
    )

    assert 200 <= resp.status_code <= 299
