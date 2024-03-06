#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.
"""Node collector metric collection."""

import argparse
import json
import logging
import os
import re
import signal
import subprocess  # nosec
import sys
import time
from functools import partial
from threading import Event
from typing import (
    Callable,
    Dict,
    Iterable,
    Literal,
    Mapping,
    NewType,
    Optional,
    Sequence,
    Union,
)

import requests
import urllib3
from requests import Session

from checkmk_kube_agent.common import (
    collector_argument_parser,
    collector_metadata,
    tcp_session,
)
from checkmk_kube_agent.container_metadata import parse_node_collector_metadata
from checkmk_kube_agent.type_defs import (
    CollectorType,
    Components,
    ContainerMetric,
    ContainerName,
    LabelName,
    LabelValue,
    MachineSections,
    MachineSectionsCollection,
    MetricCollection,
    MetricName,
    MetricValueString,
    Namespace,
    NodeName,
    PodName,
    PodUid,
    Timestamp,
    Version,
)

# urllib warnings clutter logs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

Url = NewType("Url", str)
RequestHeaders = Mapping[str, str]
CaCertPath = NewType("CaCertPath", str)
SslVerify = Union[bool, CaCertPath]


logger = logging.getLogger(__name__)


def _split_labels(raw_labels: str) -> Iterable[str]:
    """Split comma separated Kubernetes labels text into individual labels

    >>> list(_split_labels(""))
    []

    >>> list(_split_labels('mylabel="myval"'))
    ['mylabel="myval"']

    >>> list(_split_labels('mylabel1="myval1",mylabel2="myval2"'))
    ['mylabel1="myval1"', 'mylabel2="myval2"']

    >>> list(_split_labels('mylabel="myval",'))
    ['mylabel="myval"']

    >>> list(_split_labels(',mylabel="myval"'))
    ['mylabel="myval"']

    >>> list(_split_labels('mylabel="[val1,val2,val3]"'))
    ['mylabel="[val1,val2,val3]"']

    >>> list(_split_labels('mylabel1="[val1,val2,val3]",mylabel2="[val1,val2,val3]"'))
    ['mylabel1="[val1,val2,val3]"', 'mylabel2="[val1,val2,val3]"']

    >>> list(_split_labels('mylabel="[\\\\"val1\\\\",\\\\"val2\\\\",\\\\"val3\\\\"]"'))
    ['mylabel="[\\\\"val1\\\\",\\\\"val2\\\\",\\\\"val3\\\\"]"']

    >>> list(_split_labels('mylabel1="[\\\\"val1\\\\",\\\\"val2\\\\",\\\\"val3\\\\"]",'
    ... 'mylabel2="[\\\\"val1\\\\",\\\\"val2\\\\",\\\\"val3\\\\"]"'))
    ... # doctest: +NORMALIZE_WHITESPACE
    ['mylabel1="[\\\\"val1\\\\",\\\\"val2\\\\",\\\\"val3\\\\"]"',
     'mylabel2="[\\\\"val1\\\\",\\\\"val2\\\\",\\\\"val3\\\\"]"']

    """

    if not raw_labels:
        yield from ()
        return

    # csv.reader would have been a really neat solution; however, unfortunately
    # only double quotes, and not the separator characters themselves, inside
    # value strings like this:
    #     my_val="hello",another_val="you,my\"friend\""
    # are escaped, rendering it esentially unusable...
    for label in re.split(r",(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", raw_labels):
        if label:
            yield label


def _parse_labels(raw_labels: str) -> Mapping[LabelName, LabelValue]:
    """Parse open metric formatted Kubernetes labels associated with a
    container.

    >>> _parse_labels('container_label_io_kubernetes_pod_namespace="kube-system"')
    {'container_label_io_kubernetes_pod_namespace': 'kube-system'}

    >>> _parse_labels('container_label_annotation_io_kubernetes_container_'
    ... 'ports="[{\\\\"name\\\\":\\\\"dns\\\\",\\\\"containerPort\\\\":53}]"')
    ... # doctest: +NORMALIZE_WHITESPACE
    {'container_label_annotation_io_kubernetes_container_ports':
    '[{\"name\":\"dns\",\"containerPort\":53}]'}

    >>> _parse_labels("")
    {}

    """
    labels: Dict[LabelName, LabelValue] = {}

    for label in _split_labels(raw_labels):
        label_name, label_value = label.split("=")
        labels[LabelName(label_name)] = LabelValue(json.loads(label_value))

    return labels


def _parse_metrics_with_labels(
    open_metric: str, now: Timestamp
) -> Optional[ContainerMetric]:
    """Parse an individual container metric and select relevant Kubernetes
    labels.

    Containers that for some reason do not have a container name or an
    associated pod are discarded.

    If the metric has a timestamp, it is added; otherwise, the current
    timestamp is used.

    >>> _parse_metrics_with_labels(('container_cpu_cfs_periods_total'
    ... '{container_label_io_kubernetes_pod_namespace="mynamespace",'
    ... 'container_label_io_kubernetes_pod_name="mypod",'
    ... 'container_label_io_kubernetes_pod_uid="123",'
    ... 'name="k8s_POD_mypod_mynamespace_123_0"} 422 1638960636719'), 0.0)
    ... # doctest: +NORMALIZE_WHITESPACE
    ContainerMetric(container_name='k8s_POD_mypod_mynamespace_123_0',
                    namespace='mynamespace',
                    pod_uid='123',
                    pod_name='mypod',
                    metric_name='container_cpu_cfs_periods_total',
                    metric_value_string='422',
                    timestamp=1638960636.719)

    >>> _parse_metrics_with_labels(('container_cpu_cfs_periods_total'
    ... '{container_label_io_kubernetes_pod_namespace="mynamespace",'
    ... 'container_label_io_kubernetes_pod_name="mypod",'
    ... 'container_label_io_kubernetes_pod_uid="123",'
    ... 'name=""} 422'), 0.0) is None
    True

    >>> _parse_metrics_with_labels(('container_cpu_cfs_periods_total'
    ... '{container_label_io_kubernetes_pod_namespace="mynamespace",'
    ... 'container_label_io_kubernetes_pod_name="mypod",'
    ... 'container_label_io_kubernetes_pod_uid="",'
    ... 'name="k8s_POD_mypod_mynamespace_123_0"} 422'), 0.0) is None
    True
    """

    metric_name, rest = open_metric.split("{", 1)
    labels_string, timestamped_value = rest.rsplit("}", 1)
    value_string, *optional_timestamp = timestamped_value.strip().split()
    labels = _parse_labels(labels_string)

    if (container_name := labels.get(LabelName("name"))) and (
        pod_uid := labels.get(LabelName("container_label_io_kubernetes_pod_uid"))
    ):
        return ContainerMetric(
            container_name=ContainerName(container_name),
            namespace=Namespace(
                labels[LabelName("container_label_io_kubernetes_pod_namespace")]
            ),
            pod_uid=PodUid(pod_uid),
            pod_name=PodName(
                labels[LabelName("container_label_io_kubernetes_pod_name")]
            ),
            metric_name=MetricName(metric_name),
            metric_value_string=MetricValueString(value_string),
            timestamp=Timestamp(float(optional_timestamp[0]) / 1000.0)
            if optional_timestamp
            else now,
        )

    return None


def parse_raw_response(raw_response: str, now: Timestamp) -> Sequence[ContainerMetric]:
    """Parse open metric response from cAdvisor into the schema the cluster
    collector API expects.

    Only container metrics are propagated, node metrics are discarded.

    >>> parse_raw_response(("# HELP cadvisor_version_info\\n"
    ... "# TYPE container_cpu_cfs_periods_total counter\\n"), 0.0)
    []

    >>> parse_raw_response("machine_memory_bytes 1.6595398656e+10\\n", 0.0)
    []

    >>> parse_raw_response(('container_cpu_cfs_periods_total'
    ... '{container_label_io_kubernetes_pod_namespace="mynamespace",'
    ... 'container_label_io_kubernetes_pod_name="mypod",'
    ... 'container_label_io_kubernetes_pod_uid="123",'
    ... 'name="k8s_POD_mypod_mynamespace_123_0"} 422\\n'), 0.0)
    ... # doctest: +NORMALIZE_WHITESPACE
    [ContainerMetric(container_name='k8s_POD_mypod_mynamespace_123_0',
                 namespace='mynamespace',
                 pod_uid='123',
                 pod_name='mypod',
                 metric_name='container_cpu_cfs_periods_total',
                 metric_value_string='422',
                 timestamp=0.0)]

    >>> parse_raw_response("", 0.0)
    []

    """

    container_metrics = []
    for open_metric in raw_response.split("\n"):
        if "{" not in open_metric:
            # This means that the respective line does not contain any
            # Kubernetes labels, which is due to the following reasons:
            # 1. Some lines are comments that can safely be ignored. They
            #    always start with "#".
            # 2. The relevant metric does not have any labels. Such metrics
            #    include go statistics and machine metrics, which we are not
            #    interested in.
            continue
        if metric := _parse_metrics_with_labels(open_metric, now):
            container_metrics.append(metric)

    logger.debug("Parsed %d container metrics", len(container_metrics))
    return container_metrics


def read_node_collector_token() -> str:  # pragma: no cover
    """Read token from token file managed by Kubernetes."""
    with open(
        "/var/run/secrets/kubernetes.io/serviceaccount/token",
        "r",
        encoding="utf-8",
    ) as token:
        return token.read()


def parse_arguments(argv: Sequence[str]) -> argparse.Namespace:
    """Parse arguments used to configure the node collector and cluster
    collector API endpoint"""

    parser = collector_argument_parser()

    parser.add_argument(
        "--polling-interval",
        "-i",
        type=int,
        help="Interval in seconds at which to poll data",
    )
    parser.add_argument(
        "--verify-ssl",
        action="store_true",
        help="Validate cluster collector SSL certificate.",
    )
    parser.add_argument(
        "--ca-cert",
        type=str,
        help="Path to the CA certificate to validate SSL certificates against.",
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "critical"],
        default="warning",
        help="Collector log level.",
    )
    parser.add_argument(
        "--checkmk-agent-timeout",
        type=int,
        help="Checkmk Agent execution timeout in seconds",
    )
    parser.set_defaults(
        host=os.environ.get("CLUSTER_COLLECTOR_SERVICE_HOST", "127.0.0.1"),
        port=os.environ.get("CLUSTER_COLLECTOR_SERVICE_PORT_API", "10050"),
        max_retries=10,
        polling_interval=60,
        ca_cert="/etc/ca-certificates/checkmk-ca-cert.pem",
        checkmk_agent_timeout=5,
    )

    return parser.parse_args(argv)


def container_metrics_worker(
    session: Session,
    cluster_collector_base_url: Url,
    headers: RequestHeaders,
    verify: SslVerify,
    _args: argparse.Namespace,
) -> None:  # pragma: no cover
    """
    Query cadvisor api, send metrics to cluster collector
    """

    cadvisor_url = "http://localhost:8080"

    logger.info("Querying cadvisor version")
    cadvisor_version = session.get(f"{cadvisor_url}/api/v2.0/version")
    cadvisor_version.raise_for_status()
    logger.debug("cadvisor version %s", cadvisor_version.content)

    logger.info("Querying container metrics")
    cadvisor_metrics = session.get(f"{cadvisor_url}/metrics")
    cadvisor_metrics.raise_for_status()

    logger.info("Parsing and sending container metrics")
    cluster_collector_response = session.post(
        f"{cluster_collector_base_url}/update_container_metrics",
        headers=headers,
        data=MetricCollection(
            container_metrics=parse_raw_response(
                cadvisor_metrics.content.decode("utf-8"), Timestamp(time.time())
            ),
            metadata=parse_node_collector_metadata(
                collector_metadata=collector_metadata(),
                collector_type=CollectorType.CONTAINER_METRICS,
                components=Components(
                    cadvisor_version=Version(
                        json.loads(cadvisor_version.content),
                    ),
                ),
            ),
        ).json(),
        verify=verify,
    )
    _verify_and_log_cluster_collector_response(
        cluster_collector_response, "container metrics"
    )


def machine_sections_worker(
    session: Session,
    cluster_collector_base_url: Url,
    headers: RequestHeaders,
    verify: SslVerify,
    args: argparse.Namespace,
) -> None:  # pragma: no cover
    """
    Call check_mk_agent, send sections to cluster collector
    """
    logger.info("Querying Checkmk Agent for node data")
    with subprocess.Popen(  # nosec
        ["/usr/local/bin/check_mk_agent"],
        stdout=subprocess.PIPE,
    ) as process:
        (out, _err) = process.communicate(args.checkmk_agent_timeout)
        if process.returncode != 0:
            # we don't capture stderr so it's printed to stderr of this process
            # and hopefully contains a helpful error message...
            raise RuntimeError("Agent execution failed.")
        if process.stdout is None:
            raise RuntimeError("Could not read agent output")
        sections = out.decode("utf-8")

    logger.info("Parsing and sending machine sections")
    cluster_collector_response = session.post(
        f"{cluster_collector_base_url}/update_machine_sections",
        headers=headers,
        data=MachineSectionsCollection(
            sections=MachineSections(
                sections=sections,
                node_name=NodeName(os.environ["NODE_NAME"]),
            ),
            metadata=parse_node_collector_metadata(
                collector_metadata=collector_metadata(),
                collector_type=CollectorType.MACHINE_SECTIONS,
                components=Components(
                    checkmk_agent_version=Version(os.environ["CHECKMK_AGENT_VERSION"]),
                ),
            ),
        ).json(),
        verify=verify,
    )
    _verify_and_log_cluster_collector_response(
        cluster_collector_response, "machine sections"
    )


def _verify_and_log_cluster_collector_response(
    cluster_collector_response: requests.Response, component_name: str
) -> None:  # pragma: no cover
    if not 200 <= cluster_collector_response.status_code <= 299:
        logger.critical(
            "Failed to send %s to cluster collector: %s",
            component_name,
            cluster_collector_response.text,
        )
        cluster_collector_response.raise_for_status()
    else:
        logger.info("Successfully sent %s to cluster collector", component_name)


def _setup_logging(verbosity: Literal["info", "debug"]) -> None:  # pragma: no cover
    if verbosity == "debug":
        level = logging.DEBUG
    elif verbosity == "info":
        level = logging.INFO
    elif verbosity == "warning":
        level = logging.WARNING
    else:
        level = logging.CRITICAL

    # Format staying as close as possible to the api logging format
    logging.basicConfig(
        level=level, format="%(levelname)s:\t %(asctime)s - %(message)s"
    )


def _main(
    worker: Callable[
        [Session, Url, RequestHeaders, SslVerify, argparse.Namespace], None
    ],
    argv: Optional[Sequence[str]] = None,
) -> None:  # pragma: no cover
    """Run in infinite loop and execute worker function"""
    args = parse_arguments(argv or sys.argv[1:])
    _setup_logging(args.log_level)
    logger.debug("Parsed arguments: %s", args)

    protocol = "https" if args.secure_protocol else "http"

    verify = args.verify_ssl
    if verify:
        verify = CaCertPath(args.ca_cert)

    session = tcp_session(
        retries=args.max_retries,
        backoff_factor=0.1,
        timeout=(args.connect_timeout, args.read_timeout),
    )
    cluster_collector_base_url = Url(f"{protocol}://{args.host}:{args.port}")
    logger.debug("Cluster collector base url: %s", cluster_collector_base_url)

    terminated = Event()
    signal.signal(signal.SIGTERM, lambda _sig, _frame: terminated.set())

    while not terminated.is_set():
        start_time = time.time()

        headers = {
            "Authorization": f"Bearer {read_node_collector_token()}",
        }
        worker(session, cluster_collector_base_url, headers, verify, args)
        process_duration = time.time() - start_time
        logger.info("Worker finished in %.2f seconds", process_duration)

        terminated.wait(max(args.polling_interval - int(process_duration), 0))

    logger.info("Shut down gracefully")


main_container_metrics = partial(_main, container_metrics_worker)
main_machine_sections = partial(_main, machine_sections_worker)
