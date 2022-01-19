==============================================
Checkmk Kubernetes Cluster and Node Collectors
==============================================


Checkmk cluster and node collectors to monitor Kubernetes clusters.


* Free software: GNU General Public License v2


Features
--------

* Supports vanilla Kubernetes installations
* Supports Kubernetes version 1.21
* Works with *Docker* and *containerd*
* Uses cAdvisor_ to collect container metrics
* Runs the following objects on your cluster:
   * **node collector**:
        * runs as a DaemonSet on every node that has kubelet configured
        * uses cAdvisor to collect **container metrics** and fowards them to the
          cluster collector
        * uses a checkmk agent to collect **machine sections** and forwards
          them to the cluster collector
   * **cluster collector**:
        * runs as a Deployment
        * receives metrics from every node collector instance on the cluster
          and stores them in memory
        * runs an API that provides these metrics
        * can be configured to run the API in *http* or *https* mode

.. _cAdvisor: "https://github.com/google/cadvisor"

