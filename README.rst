==============================================
Checkmk Kubernetes Cluster and Node Collectors
==============================================


Checkmk cluster and node collectors to monitor Kubernetes clusters.


* Free software: GNU General Public License v2


Features
--------

* Officially supports vanilla Kubernetes installations. Unofficially also works on other flavors (e.g. AWS EKS, AKS, GKE).
* Supports Kubernetes version 1.21 to 1.23
* Works with *Docker* and *containerd*
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
* Supports PodSecurityPolicy and NetworkPolicy

Installation
------------
Please use the Helm charts provided in ``deploy/charts/checkmk`` or the manifests in ``deploy/kubernetes``. You will find detailed installation instructions there.

You can also use our `helm repository`_ to install the collectors from our latest release.

Feedback
--------
If you've got any feedback you'd like to share or are experiencing any issues, please let us know via feedback@checkmk.com or by creating a support ticket.


.. _cAdvisor: https://github.com/google/cadvisor
.. _helm repository: https://tribe29.github.io/checkmk_kube_agent/
