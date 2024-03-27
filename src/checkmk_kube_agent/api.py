#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.
"""Cluster collector API endpoints to post/get metric data."""

import argparse
import json
import logging
import os
import sys
from typing import FrozenSet, NewType, NoReturn, Optional, Sequence

import gunicorn.app.base  # type: ignore[import]
import pydantic
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from requests import Session

from checkmk_kube_agent.common import (
    TCPTimeout,
    collector_argument_parser,
    collector_metadata,
    tcp_session,
)
from checkmk_kube_agent.dedup_ttl_cache import DedupTTLCache
from checkmk_kube_agent.type_defs import (
    ClusterCollectorMetadata,
    ContainerMetric,
    MachineSections,
    MachineSectionsCollection,
    Metadata,
    MetricCollection,
    NodeCollectorMetadata,
    NodeName,
    RaiseFromError,
    Response,
    TokenError,
    TokenReview,
)

app = FastAPI()
LOGGER = logging.getLogger(__name__)

http_bearer_scheme = HTTPBearer()

ContainerMetricKey = NewType("ContainerMetricKey", str)
MetadataKey = NewType("MetadataKey", str)

KUBERNETES_SERVICE_HOST = os.environ.get("KUBERNETES_SERVICE_HOST")
KUBERNETES_SERVICE_PORT_HTTPS = os.environ.get("KUBERNETES_SERVICE_PORT_HTTPS")


def container_metric_key(metric: ContainerMetric) -> ContainerMetricKey:
    """Key function to determine unique key for container metrics"""
    return ContainerMetricKey(f"{metric.container_name}:{metric.metric_name}")


def metadata_key(metadata: NodeCollectorMetadata) -> MetadataKey:
    """Key function to determine unique key for metadata"""
    return MetadataKey(f"{metadata.node}:{metadata.collector_type}")


def read_api_token() -> str:  # pragma: no cover
    """Read token from token file managed by Kubernetes."""
    with open(
        "/var/run/secrets/kubernetes.io/serviceaccount/token",
        "r",
        encoding="utf-8",
    ) as token_file:
        return token_file.read()


def _raise_from_token_error(
    token_review_response: bytes,
    token: str,
    token_error: TokenError,
    logger: logging.Logger,
) -> NoReturn:
    redacted_token_review_response = token_review_response.replace(
        token.encode("utf-8"), b"***token***"
    )
    logger.error(redacted_token_review_response)
    raise HTTPException(
        status_code=token_error.status_code,
        detail=f"{token_error.message} See logs for TokenReview.",
        headers={"WWW-Authenticate": "Bearer"},
    ) from token_error.exception


def _check_token_review(
    response: Response,
    serviceaccount_whitelist: FrozenSet[str],
) -> Optional[TokenError]:
    if response.status_code < 200 or response.status_code > 299:
        return TokenError(
            status_code=response.status_code,
            message="HTTP status code indicates error.",
        )
    return _check_token_review_content(response.content, serviceaccount_whitelist)


def _check_token_review_content(
    content: bytes,
    serviceaccount_whitelist: FrozenSet[str],
) -> Optional[TokenError]:
    try:
        token_review_status = TokenReview.parse_obj(json.loads(content)).status
    except (json.JSONDecodeError, pydantic.ValidationError) as exception:
        return TokenError(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            message="Error while parsing TokenReview!",
            exception=exception,
        )

    if not token_review_status.authenticated:
        return TokenError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="Invalid authentication credentials!",
        )

    if token_review_status.user is None:
        return TokenError(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            message="No user in token_review_response!",
        )

    try:
        namespace, serviceaccount = token_review_status.user.username.split(":")[-2:]
    except ValueError as exception:
        return TokenError(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            message="Username has unexpected format!",
            exception=exception,
        )

    if f"{namespace}:{serviceaccount}" not in serviceaccount_whitelist:
        return TokenError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message=f"Access denied for Service Account {serviceaccount} "
            f"in Namespace {namespace}!",
        )
    return None


def _join_host_port(host: str, port: str) -> str:  # pragma: no cover
    # reference implementation
    # https://cs.opensource.google/go/go/+/refs/tags/go1.22.1:src/net/ipsock.go;l=235
    if ":" in host:
        return f"[{host}]:{port}"
    return f"{host}:{port}"


def authenticate(
    token: HTTPAuthorizationCredentials,
    *,
    kubernetes_service_host: Optional[str],
    kubernetes_service_port_https: Optional[str],
    session: Session,
    serviceaccount_whitelist: FrozenSet[str],
    raise_from_token_error: RaiseFromError = lambda response, token, error: _raise_from_token_error(
        response,
        token,
        error,
        LOGGER,
    ),
) -> HTTPAuthorizationCredentials:
    """Verify whether the Service Account has access to GET/POST from/to the
    cluster collector API.

    The validity of the `token` is verified by the Kubernetes Token Review API.
    Then, it is verified whether the corresponding Service Account is
    whitelisted."""

    # reference implementation:
    # https://github.com/kubernetes/kubernetes/blob/67bde9a1023d1805e33d698b28aa6fad991dfb39/staging/src/k8s.io/client-go/rest/config.go#L507-L541
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
            f"https://{_join_host_port(kubernetes_service_host, kubernetes_service_port_https)}/"
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
    token_error = _check_token_review(
        Response(token_review_response.status_code, token_review_response.content),
        serviceaccount_whitelist,
    )
    if token_error is not None:
        raise_from_token_error(
            token_review_response.content,
            token.credentials,
            token_error,
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
    machine_sections: MachineSectionsCollection,
    token: str = Depends(authenticate_post),  # pylint: disable=unused-argument
) -> None:
    """Update sections for the kubernetes machines"""
    app.state.node_collector_metadata_queue.put(machine_sections.metadata)
    app.state.machine_sections_queue.put(machine_sections.sections)


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
    app.state.node_collector_metadata_queue.put(metrics.metadata)
    for metric in metrics.container_metrics:
        app.state.container_metric_queue.put(metric)


@app.get("/container_metrics")
def send_container_metrics(
    token: str = Depends(authenticate_get),  # pylint: disable=unused-argument
) -> Sequence[ContainerMetric]:
    """Get all available container metrics"""
    return app.state.container_metric_queue.get_all()


@app.get("/metadata")
def send_metadata(
    token: str = Depends(authenticate_get),  # pylint: disable=unused-argument
) -> Metadata:
    """Get metadata on cluster and node collectors.

    May be used to verify compatibility."""
    return Metadata(
        cluster_collector_metadata=app.state.metadata,
        node_collector_metadata=app.state.node_collector_metadata_queue.get_all(),
    )


def parse_arguments(argv: Sequence[str]) -> argparse.Namespace:
    """Parse arguments used to configure the API endpoint and the DedupQueue"""

    parser = collector_argument_parser()

    parser.add_argument(
        "--ssl-keyfile",
        required="--secure-protocol" in argv,
        help="Path to the SSL key file for HTTPS connections",
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
        choices=["debug", "info", "warning", "error", "critical"],
        help="gunicorn log level.",
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
    metadata: ClusterCollectorMetadata,
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
    app_.state.node_collector_metadata_queue = DedupTTLCache[
        MetadataKey, NodeCollectorMetadata
    ](
        key=metadata_key,
        maxsize=10000,  # Kubernetes clusters can have a max of 5000 nodes.
        # Each node collector daemonset sends their own metadata to this queue
        ttl=cache_ttl,
    )
    app_.state.metadata = metadata
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
        metadata=ClusterCollectorMetadata(**dict(collector_metadata())),
    )

    options = {
        "bind": f"{args.host}:{args.port}",
        "workers": 1,
        "worker_class": "uvicorn.workers.UvicornWorker",
        "loglevel": args.log_level,
        "accesslog": "-",
    }
    if args.secure_protocol:
        options.update(
            {
                "keyfile": args.ssl_keyfile,
                "certfile": args.ssl_certfile,
            }
        )

    StandaloneApplication(app, options).run()


class StandaloneApplication(
    gunicorn.app.base.BaseApplication
):  # pylint: disable=abstract-method
    """
    normally gunicorn is started from the command line, but we want it to fully
    integrate into our own script.
    https://docs.gunicorn.org/en/stable/custom.html#custom-application
    """

    def __init__(self, app_, options=None) -> None:
        self.options = options or {}
        self.application = app_
        super().__init__()

    def load_config(self):
        """load config"""
        for key, value in self.options.items():
            self.cfg.set(key, value)

    def load(self):
        """load app"""
        return self.application


if __name__ == "__main__":
    main()
