==============================================
Checkmk Kubernetes Cluster and Node Collectors
==============================================

You can deploy the Checkmk Kubernetes Cluster and Node Collectors using the manifests here.
Note: We recommend using Helm charts as they are less error-prone. We do not provide support for installation via manifests.

Short installation guide
------------------------

#. Download ``00_namespace.yaml``, ``checkmk-serviceaccount.yaml``, ``cluster-collector.yaml``, ``node-collector.yaml``, ``service.yaml``

#. Optional: Download ``network-policy.yaml`` and ``pod-security-policy.yaml``, if this is required in your cluster.

#. Replace the image tags *main_<YYYY.MM.DD>* in ``cluster-collector.yaml``, ``node-collector.yaml``
   You can find possible tags here: https://hub.docker.com/r/checkmk/kubernetes-collector/tags

#. Define communication method for Cluster Collector

   #. NodePort: Enabled by default with NodePort 30035, no change needed.

   #. Ingress: As this depends highly on your Kubernetes set-up, this needs to be entirely configured by you in the *service.yaml* and *ingress.yaml*. Example instructions will follow.

#. Deploy to your cluster

   .. code-block::

      kubectl apply -f .



Validation:

* If everything was successful, you should have one pod called ``cluster-collector`` and on each node pods called ``node-collector-container-metrics`` and ``node-collector-machine-sections``

  .. code-block::

     kubectl get pods -n checkmk-monitoring

* You should have the internal service ``cluster-collector`` and either a NodePort (default 30035) or the service you configured running

  .. code-block::

     kubectl get svc -n checkmk-monitoring

Checkmk set-up guide
--------------------

Prerequisites:

* The URL of the Kubernetes API server

* The token of Checkmk service account.

  .. code-block::

      kubectl get secret $(kubectl get serviceaccount checkmk -o=jsonpath='{.secrets[*].name}' -n checkmk-monitoring) -n checkmk-monitoring -o=jsonpath='{.data.token}' | base64 --decode

* The certificate of the Checkmk service account.

  .. code-block::

      kubectl get secret $(kubectl get serviceaccount checkmk -o=jsonpath='{.secrets[*].name}' -n checkmk-monitoring) -n checkmk-monitoring -o=jsonpath='{.data.ca\.crt}' | base64 --decode

* The *Checkmk Kubernetes Collectors* deployed and the URL under which the *Cluster Collector* is reachable

* Recommended: Secure communication to the *Cluster Collector* (see details in *Additional topics*)

#. **Preparing your Checkmk**

   #. Create a piggyback source host with *IP address family* set to *No IP* (this host will contain cluster-level services and metrics)

   #. Create a folder, which will later contain all Kubernetes objects

   #. Configure the dynamic host management: *Setup → Hosts (Dynamic host management) → Add connection*

      * Enter *Title* and click *show more* for *Connection Properties*

      * *Connection Properties → Piggyback creation options → Add new element*

      * In *Create hosts in*: select the folder you just created

      * Select *Automatically delete hosts without piggyback data*

      * Under *Restrict source hosts*: enter the name of your piggyback source host(s)

      * Tick *Service discovery → Discover services during creation*

   #. Optional: add the certificate of the Checkmk service account (depends on your cluster / set-up)

      * *Setup → Global Settings → Trusted certificate authorities for SSL → Add new CA certificate or chain*

   #. Optional: add the token of the Checkmk service account to the password store

      * *Setup → General → Passwords → Add pasword*

#. **Setting up the connection**

   #. Set up the Kubernetes 2.0 ruleset: *Setup → Agents (VM, Cloud, Container) → Kubernetes → Add rule*

   #. Name your cluster (will be included in the object names)

   #. Add the token of the Checkmk service account to be able to retrieve data. We recommend using the password store for this.

   #. Configure the *API server connection endpoint*: enter the URL (and port), where your API server is located

      * You can set *SSL certficate verification* to *Verify the certificate*, if you added the certificate as mentioned in the previous section

   #. Configure the *Collector NodePort / Ingress endpoint*

      * NodePort: URL of a node + port (default: 30035)

      * If you set-up communication via HTTPS for the cluster collector (see section below), you can set *SSL certficate verification* to *Verify the certificate*

   #. You can exclude namespaces or limit your monitoring to a few namespaces. Cluster-wide components, e.g. nodes, will still be retrieved though

   #. Under *Explicit host* in *Conditions* add the name of piggyback source host.

   #. Activate changes. You are done.

Additional topics
-----------------

**Secure commmunication**

Secure communications to and between the *Checkmk Kubernetes Collectors* can be achieved in various ways.
You can use Kubernetes native methods, e.g. a properly configured Ingress for external communication and a
ServiceMesh for internal communication. This has to be done by you / your cluster administrator.

Alternatively, you can use the mechanisms provided by *Checkmk Kubernetes Collectors* to secure both the communication from outside
to the *Cluster Collector* API as well as the communication between the *Node Collectors* and the *Cluster Collector*.

#. Search for the HTTPS comment in ``node-collector.yaml`` and ``cluster-collector.yaml`` and follow the instructions there

#. Download the ``secret.yaml`` and add certificates

   #. For *cluster-collector-key* and *cluster-collector-cert*: Add certificates with the service: [cluster-collector-service].[collector-namespace] as FQDN following and the hostname/ingress as AltName

   #. Add the respective CA certificate to *checkmkCaCert* and add that in Checkmk as well (Trusted certificate authorities for SSL)

.. _cAdvisor: "https://github.com/google/cadvisor"
