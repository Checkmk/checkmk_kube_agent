#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

"""Cluster collector API endpoints to post/get metric data."""

import argparse
import json
import os
import sys
from typing import FrozenSet, NewType, Optional, Sequence

import uvicorn  # type: ignore[import]
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from requests import Session

from checkmk_kube_agent.common import TCPTimeout, collector_argument_parser, tcp_session
from checkmk_kube_agent.dedup_ttl_cache import DedupTTLCache
from checkmk_kube_agent.type_defs import (
    ContainerMetric,
    MachineSections,
    MetricCollection,
    NodeName,
)

app = FastAPI()

http_bearer_scheme = HTTPBearer()

ContainerMetricKey = NewType("ContainerMetricKey", str)

KUBERNETES_SERVICE_HOST = os.environ.get("KUBERNETES_SERVICE_HOST")
KUBERNETES_SERVICE_PORT_HTTPS = os.environ.get("KUBERNETES_SERVICE_PORT_HTTPS")


def container_metric_key(metric: ContainerMetric) -> ContainerMetricKey:
    """Key function to determine unique key for container metrics"""
    return ContainerMetricKey(f"{metric.container_name}:{metric.metric_name}")


def read_api_token() -> str:  # pragma: no cover
    """Read token from token file managed by Kubernetes."""
    with open(
        "/var/run/secrets/kubernetes.io/serviceaccount/token",
        "r",
        encoding="utf-8",
    ) as token_file:
        return token_file.read()


def authenticate(
    token: HTTPAuthorizationCredentials,
    *,
    kubernetes_service_host: Optional[str],
    kubernetes_service_port_https: Optional[str],
    session: Session,
    serviceaccount_whitelist: FrozenSet[str],
) -> HTTPAuthorizationCredentials:
    """Verify whether the Service Account has access to GET/POST from/to the
    cluster collector API.

    The validity of the `token` is verified by the Kubernetes Token Review API.
    Then, it is verified whether the corresponding Service Account is
    whitelisted."""

    api_token = read_api_token()

    if not kubernetes_service_host or not kubernetes_service_port_https:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to verify authentication credentials: cannot read "
            "Kubernetes API hostname and port.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_review_response = session.post(
        (
            f"https://{kubernetes_service_host}:{kubernetes_service_port_https}/"
            "apis/authentication.k8s.io/v1/tokenreviews"
        ),
        headers={
            "Authorization": f"Bearer {api_token}",
        },
        data=json.dumps(
            {
                "kind": "TokenReview",
                "apiVersion": "authentication.k8s.io/v1",
                "spec": {
                    "token": token.credentials,
                },
            }
        ),
        verify="/run/secrets/kubernetes.io/serviceaccount/ca.crt",
    )

    if (
        token_review_response.status_code < 200
        or token_review_response.status_code > 299
    ):
        raise HTTPException(
            status_code=token_review_response.status_code,
            detail=json.loads(token_review_response.content),
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_review_response_status = json.loads(token_review_response.content)["status"]

    if not token_review_response_status.get("authenticated"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    namespace, serviceaccount = token_review_response_status["user"]["username"].split(
        ":"
    )[-2:]

    if f"{namespace}:{serviceaccount}" not in serviceaccount_whitelist:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Access denied for Service Account {serviceaccount} in "
            f"Namespace {namespace}.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token


async def authenticate_post(
    token: HTTPAuthorizationCredentials = Depends(http_bearer_scheme),
    *,
    kubernetes_service_host: Optional[str] = KUBERNETES_SERVICE_HOST,
    kubernetes_service_port_https: Optional[str] = KUBERNETES_SERVICE_PORT_HTTPS,
) -> HTTPAuthorizationCredentials:
    """Verify whether the requestor has write access to the cluster collector
    API."""

    return authenticate(
        token,
        kubernetes_service_host=kubernetes_service_host,
        kubernetes_service_port_https=kubernetes_service_port_https,
        session=app.state.tcp_session,
        serviceaccount_whitelist=app.state.writer_whitelist,
    )


async def authenticate_get(
    token: HTTPAuthorizationCredentials = Depends(http_bearer_scheme),
    *,
    kubernetes_service_host: Optional[str] = KUBERNETES_SERVICE_HOST,
    kubernetes_service_port_https: Optional[str] = KUBERNETES_SERVICE_PORT_HTTPS,
) -> HTTPAuthorizationCredentials:
    """Verify whether the requestor has read access to the cluster collector
    API."""

    return authenticate(
        token,
        kubernetes_service_host=kubernetes_service_host,
        kubernetes_service_port_https=kubernetes_service_port_https,
        session=app.state.tcp_session,
        serviceaccount_whitelist=app.state.reader_whitelist,
    )


@app.get("/")
def root(
    token: str = Depends(authenticate_get),  # pylint: disable=unused-argument
) -> RedirectResponse:
    """Root endpoint redirecting to API documentation"""
    return RedirectResponse("/docs")


@app.get("/health")
def health() -> JSONResponse:
    """Basic endpoint to query API health"""
    return JSONResponse({"status": "available"})


@app.post("/update_machine_sections")
def update_machine_sections(
    machine_sections: MachineSections,
    token: str = Depends(authenticate_post),  # pylint: disable=unused-argument
) -> None:
    """Update sections for the kubernetes machines"""
    app.state.machine_sections_queue.put(machine_sections)


@app.get("/machine_sections")
def send_machine_sections(
    token: str = Depends(authenticate_get),  # pylint: disable=unused-argument
) -> Sequence[MachineSections]:
    """Get all available host metrics"""
    return app.state.machine_sections_queue.get_all()


@app.post("/update_container_metrics")
def update_container_metrics(
    metrics: MetricCollection,
    token: str = Depends(authenticate_post),  # pylint: disable=unused-argument
) -> None:
    """Update metrics for containers"""
    for metric in metrics.container_metrics:
        app.state.container_metric_queue.put(metric)


@app.get("/container_metrics")
def send_container_metrics(
    token: str = Depends(authenticate_get),  # pylint: disable=unused-argument
) -> Sequence[ContainerMetric]:
    """Get all available container metrics"""
    return app.state.container_metric_queue.get_all()


def parse_arguments(argv: Sequence[str]) -> argparse.Namespace:
    """Parse arguments used to configure the API endpoint and the DedupQueue"""

    parser = collector_argument_parser()

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
        "--reader-whitelist",
        help="Service Accounts that have access to query data from the cluster "
        "collector API GET endpoints. Should be a comma separated list of "
        "NAMESPACE:SERVICEACCOUNT values. Defaults to "
        "checkmk-monitoring:checkmk-server.",
    )
    parser.add_argument(
        "--writer-whitelist",
        help="Service Accounts that have access to post data to the cluster "
        "collector API POST endpoints. Should be a comma separated list of "
        "NAMESPACE:SERVICEACCOUNT values. Defaults to "
        "checkmk-monitoring:node-collector.",
    )
    parser.add_argument(
        "--cache-maxsize",
        type=int,
        help="Specify the maximum number of metric entries the cluster collector "
        "can hold at a time. Once maxsize is reached, the oldest metric entry "
        "will be discarded before a new entry is added",
    )
    parser.add_argument(
        "--cache-ttl",
        type=int,
        help="Specify the time-to-live (seconds) entries are persisted in the "
        "cache. Entries exceeding ttl are removed from the cache.",
    )
    parser.add_argument(
        "--log-level",
        choices=["trace", "debug", "info", "warning", "error", "critical"],
        help="Uvicorn log level.",
    )

    parser.set_defaults(
        host="127.0.0.1",
        port=10050,
        reader_whitelist="checkmk-monitoring:checkmk",
        writer_whitelist="checkmk-monitoring:node-collector",
        cache_maxsize=10000,
        cache_ttl=120,
        log_level="error",
    )

    return parser.parse_args(argv)


def _init_app_state(
    app_,
    *,
    cache_maxsize: int,
    cache_ttl: int,
    reader_whitelist: Sequence[str],
    writer_whitelist: Sequence[str],
    tcp_timeout: TCPTimeout,
) -> None:
    container_metric_queue = DedupTTLCache[ContainerMetricKey, ContainerMetric](
        key=container_metric_key,
        maxsize=cache_maxsize,
        ttl=cache_ttl,
    )
    app_.state.container_metric_queue = container_metric_queue
    app_.state.machine_sections_queue = DedupTTLCache[NodeName, MachineSections](
        key=lambda x: x.node_name,
        maxsize=cache_maxsize,
        ttl=cache_ttl,
    )
    app_.state.reader_whitelist = frozenset(reader_whitelist)
    app_.state.writer_whitelist = frozenset(writer_whitelist)
    app_.state.tcp_session = tcp_session(timeout=tcp_timeout)


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Cluster collector API main function: start API"""
    args = parse_arguments(argv or sys.argv[1:])

    _init_app_state(
        app,
        cache_maxsize=args.cache_maxsize,
        cache_ttl=args.cache_ttl,
        reader_whitelist=args.reader_whitelist.split(","),
        writer_whitelist=args.writer_whitelist.split(","),
        tcp_timeout=(args.connect_timeout, args.read_timeout),
    )

    if args.secure_protocol:
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            ssl_keyfile=args.ssl_keyfile,
            ssl_keyfile_password=args.ssl_keyfile_password,
            ssl_certfile=args.ssl_certfile,
            log_level=args.log_level,
        )
    else:
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_level=args.log_level,
        )


if __name__ == "__main__":
    main()
