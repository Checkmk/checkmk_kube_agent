from typing import DefaultDict
from collections import defaultdict
import re


def test_sections():
    """
    very basic check
    """
    sections: DefaultDict[str, int] = defaultdict(int)
    with open("/tmp/agentoutput") as handler:
        for line in handler:
            if match := re.match("<<<([^<>]+)>>>", line):
                section_name = match.groups()[0].split(":")[0]
                sections[section_name] += 1
    assert sections == {
        "check_mk": 3,
        "cpu": 3,
        "df": 6,
        "diskstat": 3,
        "kernel": 3,
        "mem": 3,
        "uptime": 3,
        #
        "kube_cluster_details_v1": 1,
        "kube_collectors_metadata_v1": 1,
        "kube_node_count_v1": 1,
        "kube_processing_logs_v1": 1,
        #
        "kube_replicas_v1": 2,
        "kube_deployment_conditions_v1": 2,
        "kube_deployment_info_v1": 2,
        "kube_deployment_strategy_v1": 2,
        #
        "kube_node_conditions_v1": 3,
        "kube_node_container_count_v1": 3,
        "kube_pod_init_containers_v1": 3,
        "kube_node_info_v1": 3,
        "kube_node_kubelet_v1": 3,
        #
        "kube_allocatable_pods_v1": 4,
        "kube_allocatable_cpu_resource_v1": 4,
        "kube_allocatable_memory_resource_v1": 4,
        #
        "kube_pod_resources_v1": 6,
        #
        "kube_performance_cpu_v1": 22,
        "kube_performance_memory_v1": 22,
        "kube_pod_conditions_v1": 22,
        "kube_pod_container_specs_v1": 22,
        "kube_pod_containers_v1": 22,
        "kube_pod_info_v1": 22,
        "kube_pod_init_container_specs_v1": 22,
        "kube_pod_lifecycle_v1": 22,
        "kube_start_time_v1": 22,
        #
        "kube_cpu_resources_v1": 28,
        "kube_memory_resources_v1": 28,
    }


# def test_piggyback():
#     """
#     very basic check
#     """
#     piggybacks: DefaultDict[str, int] = defaultdict(int)
#     with open("/tmp/agentoutput") as handler:
#         for line in handler:
#             if match := re.match("<<<<([^<>]+)>>>>", line):
#                 piggyback_name = match.groups()[0].split(":")[0]
#                 piggybacks[piggyback_name] += 1
#     assert piggybacks == {}
