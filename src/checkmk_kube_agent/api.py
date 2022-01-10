#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

"""Cluster collector API endpoints to post/get metric data."""

import argparse
import sys
from typing import NewType, Optional, Sequence

import uvicorn  # type: ignore[import]
from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse

from checkmk_kube_agent.dedup_queue import DedupQueue
from checkmk_kube_agent.type_defs import ContainerMetric, MetricCollection

app = FastAPI()

ContainerMetricKey = NewType("ContainerMetricKey", str)


def container_metric_key(metric: ContainerMetric) -> ContainerMetricKey:
    """Key function to determine unique key for container metrics"""
    return ContainerMetricKey(f"{metric.container_name}:{metric.metric_name}")


@app.get("/")
def root() -> RedirectResponse:
    """Root endpoint redirecting to API documentation"""
    return RedirectResponse("/docs")


@app.get("/health")
def health() -> JSONResponse:
    """Basic endpoint to query API health"""
    return JSONResponse({"status": "available"})


@app.post("/update_container_metrics")
def update_container_metrics(metrics: MetricCollection) -> None:
    """Update metrics for containers"""
    for metric in metrics.container_metrics:
        app.state.container_metric_queue.put(metric)


@app.get("/container_metrics")
def send_container_metrics() -> Sequence[ContainerMetric]:
    """Get all available container metrics"""
    return app.state.container_metric_queue.get_all()


def parse_arguments(argv: Sequence[str]) -> argparse.Namespace:
    """Parse arguments used to configure the API endpoint and the DedupQueue"""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--host",
        "-s",
        help="Host IP address on which to start the API",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        help="Port",
    )
    parser.add_argument(
        "--secure-protocol",
        action="store_true",
        help="Use secure protocol (HTTPS)",
    )
    parser.add_argument(
        "--ssl-keyfile",
        required="--secure-protocol" in argv,
        help="Path to the SSL key file for HTTPS connections",
    )
    parser.add_argument(
        "--ssl-keyfile-password",
        required="--secure-protocol" in argv,
        help="Password for the SSL key file for HTTPS connections",
    )
    parser.add_argument(
        "--ssl-certfile",
        required="--secure-protocol" in argv,
        help="Path to the SSL certificate file for HTTPS connections",
    )
    parser.add_argument(
        "--queue-maxsize",
        type=int,
        help="Specify the maximum number of metric entries the cluster agent "
        "can hold at a time. Once maxsize is reached, the oldest metric entry "
        "will be discarded before a new entry is added",
    )

    parser.set_defaults(
        host="127.0.0.1",
        port=10050,
        queue_maxsize=10000,
    )

    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Cluster collector API main function: start API"""
    args = parse_arguments(argv or sys.argv[1:])
    container_metric_queue = DedupQueue[ContainerMetricKey, ContainerMetric](
        container_metric_key,
        maxsize=args.queue_maxsize,
    )
    app.state.container_metric_queue = container_metric_queue

    if args.secure_protocol:
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            ssl_keyfile=args.ssl_keyfile,
            ssl_keyfile_password=args.ssl_keyfile_password,
            ssl_certfile=args.ssl_certfile,
        )
    else:
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
        )


if __name__ == "__main__":
    main()
