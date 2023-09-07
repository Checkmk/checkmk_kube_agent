==============================================
Checkmk Kubernetes Cluster and Node Collectors
==============================================


Checkmk cluster and node collectors to monitor Kubernetes clusters.


* Free software: GNU General Public License v2


Installation
--------

You can use our `helm repository`_ to install the collectors from our latest release.
Detailed instructions can be found in our `official docs`_.


Support policy
--------

Please read our `official docs`_ for information regarding supported Kubernetes versions 
and supported Kubernetes distros.


Features
--------

* Monitor Kubernetes clusters
* Uses `cAdvisor`_ to collect container metrics
* Runs the following objects on your cluster:
   * **node collector**:
        * runs as a DaemonSet on every node that has kubelet configured
        * uses cAdvisor to collect **container metrics** and fowards them to the
          cluster collector
        * uses a Checkmk agent to collect **machine sections** and forwards
          them to the cluster collector
   * **cluster collector**:
        * runs as a Deployment
        * receives metrics from every node collector instance on the cluster
          and stores them in memory
        * runs an API that provides these metrics
        * can be configured to run the API in *http* or *https* mode
* Supports PodSecurityPolicy (up to Kubernetes 1.24) and NetworkPolicy

.. _cAdvisor: https://github.com/google/cadvisor
.. _helm repository: https://checkmk.github.io/checkmk_kube_agent/
.. _official docs: https://docs.checkmk.com/latest/en/monitoring_kubernetes.html