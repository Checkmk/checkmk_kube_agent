# checkmk

Installs the checkmk Kubernetes agent.

_Note: This chart is relatively young. Please use with care, read the documentation carefully, and file Issues or Pull Requests if required._

## Prerequisites

- Kubernetes 1.19+
- Helm 3+

## Add the Helm Repository

```console
helm repo add tribe29 https://tribe29.github.io/checkmk_kube_agent
helm repo update
```

_See [helm repo](https://helm.sh/docs/helm/helm_repo/) for command documentation._

## Install or Upgrade Chart

To install or upgrade the Helm chart, use the following command template:

```console
helm upgrade --install --create-namespace -n [RELEASE_NAMESPACE] [RELEASE_NAME] [-f values.custom.yaml] tribe29/checkmk
```

**At the moment, we only have pre-releases of our collectors available. In order to install them, you must explicitly agree to deploy development releases, or specify an explicit version that should be deployed.**

```console
# example to deploy development release
helm upgrade --install --create-namespace -n checkmk-monitoring checkmk tribe29/checkmk --devel

# example to deploy explicit version
helm upgrade --install --create-namespace -n checkmk-monitoring checkmk tribe29/checkmk --version 1.0.0-beta.2
```

Optionally, you can pass `-f values.custom.yaml` to overwrite default values of the chart specified in your custom `values.custom.yaml` file.

Note that the flag `--create-namespace` will create the specified namespace `RELEASE_NAMESPACE` if it does not yet exists.

_See [configuration](#configuration) below._

_See [helm install](https://helm.sh/docs/helm/helm_install/) for command documentation._

## Uninstall Chart

```console
helm uninstall -n [RELEASE_NAMESPACE] [RELEASE_NAME]
```

This removes all the Kubernetes components associated with the chart and deletes the release.

_See [helm uninstall](https://helm.sh/docs/helm/helm_uninstall/) for command documentation._

## Preview Helm changes

The [helm-diff](https://github.com/databus23/helm-diff) plugin gives us the possibility to preview what a `helm upgrade` would change.

Install it via `helm plugin install https://github.com/databus23/helm-diff`, then you can run the following prior to an install or upgrade command:

```console
# Helm requires helm-diff plugin
helm diff upgrade --install -n [RELEASE_NAMESPACE] [RELEASE_NAME] [-f values.yaml] tribe29/checkmk
```

## Render Helm templates

To render plain Kubernetes manifests from the Helm chart, run:

```console
helm template -n [RELEASE_NAMESPACE] [RELEASE_NAME] tribe29/checkmk
```

Note that, as also with the other commands (except `helm uninstall`), you can speficy additional helm value files via `-f [MY_CUSTOM_VALUES_FILE]`, which configures the Helm chart using the custom configuration specified.

## Configuration

See [Customizing the Chart Before Installing](https://helm.sh/docs/intro/using_helm/#customizing-the-chart-before-installing). To see all configurable options with detailed comments:

```console
helm show values tribe29/checkmk
```
### Configure the Checkmk Kubernetes Collectors
By default, the *Checkmk Cluster Collector service* is not exposed and communicates using HTTP. Depending on your requirements, either expose the  *Checkmk Cluster Collector service* via NodePort or Ingress.

For communication via NodePort:
- Set *clusterCollector.service.type: NodePort*
- Uncomment *clusterCollector.service.nodePort*

For communication via Ingress: Adapt the configuration in *clusterCollector.ingress* as needed.

#### Image tags
You can find possible tags here: https://hub.docker.com/r/checkmk/kubernetes-collector/tags

#### Secure commmunication

Secure communications to and between the *Checkmk Kubernetes Collectors* can be achieved in various ways.
You can use Kubernetes native methods, e.g. a properly configured Ingress for external communication and a
ServiceMesh for internal communication. This has to be done by you / your cluster administrator.

Alternatively, you can use the mechanisms provided by *Checkmk Kubernetes Collectors* to secure both the communication from outside
to the *Cluster Collector* API as well as the communication between the *Node Collectors* and the *Cluster Collector*.

1. Set *tlsCommunication.enabled: true* and *tlsCommunication.verifySsl: true*
2. Add certificates in *tlsCommunication*
   - For *clusterCollectorKey* and *clusterCollectorCert*: Add certificates with the service (`[cluster-collector-service].[collector-namespace]`) as FQDN following and the hostname/ingress as AltName
   - Add the respective CA certificate to *checkmkCaCert* and add that in Checkmk as well (Trusted certificate authorities for SSL)

### Multiple releases

The same chart can be used to run multiple checkmk instances in the same cluster (or even the same namespace) if required. To achieve this, just rename the `RELEASE_NAME` when installing.

### Configure Checkmk

#### Prerequisites

* The URL of the Kubernetes API server
* The token of Checkmk service account. Use the command provided by helm after succesful deployment. Alternatively adapt this one.
  ```console
  kubectl get secret $(kubectl get serviceaccount [SERVICEACCOUNT] -o=jsonpath='{.secrets[*].name}' -n [NAMESPACE]) -n [NAMESPACE] -o=jsonpath='{.data.token}' | base64 --decode
  ```
* The certificate of the Checkmk service account. Use the command provided by helm after succesful deployment. Alternatively adapt this one.
  ```console
  kubectl get secret $(kubectl get serviceaccount [SERVICEACCOUNT] -o=jsonpath='{.secrets[*].name}' -n [NAMESPACE]) -n [NAMESPACE] -o=jsonpath='{.data.ca\.crt}' | base64 --decode
  ```
* The *Checkmk Kubernetes Collectors* deployed and the URL under which the *Cluster Collector* is reachable
* Recommended: Secure communication to the *Cluster Collector* (see details in *Additional topics*)

#### Preparing your Checkmk

1. Create a piggyback source host with *IP address family* set to *No IP* (this host will contain cluster-level services and metrics)
2. Create a folder, which will later contain all Kubernetes objects
3. Configure the dynamic host management: *Setup → Hosts (Dynamic host management) → Add connection*
4. Enter *Title* and click *show more* for *Connection Properties*
   - *Connection Properties → Piggyback creation options → Add new element*
   - In *Create hosts in*: select the folder you just created
   - Select *Automatically delete hosts without piggyback data*
   - Under *Restrict source hosts*: enter the name of your piggyback source host(s)
   - Tick *Service discovery → Discover services during creation*
5. Optional: add the certificate of the Checkmk service account (depends on your cluster / set-up)
   - *Setup → Global Settings → Trusted certificate authorities for SSL → Add new CA certificate or chain*
6. Optional: add the token of the Checkmk service account to the password store
   - *Setup → General → Passwords → Add pasword*

#### Setting up the connection

1. Set up the Kubernetes 2.0 ruleset: *Setup → Agents (VM, Cloud, Container) → Kubernetes → Add rule*
2. Name your cluster (will be included in the object names)
3. Add the token of the Checkmk service account to be able to retrieve data. We recommend using the password store for this.
4. Configure the *API server connection endpoint*: enter the URL (and port), where your API server is located
   - You can set *SSL certficate verification* to *Verify the certificate*, if you added the certificate as mentioned in the previous section
5. Configure the *Collector NodePort / Ingress endpoint*
   - NodePort: URL of a node + port (default: 30035)
   - If you set-up communication via HTTPS for the cluster collector (see section below), you can set *SSL certficate verification* to *Verify the certificate*
6. You can exclude namespaces or limit your monitoring to a few namespaces. Cluster-wide components, e.g. nodes, will still be retrieved though
7. Under *Explicit host* in *Conditions* add the name of piggyback source host.
8. Activate changes. You are done.

## Debug

To debug in-cluster, you can launch a debug pod with network tools via

```console
kubectl -n [RELEASE_NAMESPACE] run -it debug --rm --image wbitt/network-multitool --restart=Never -- sh
```

and, with the token of the service account names `[RELEASE_NAME]-checkmk`, issue queries against the `cluster-collector`:

```console
# non-TLS
curl -H "Authorization: Bearer <TOKEN>" <RELEAE_NAME>-cluster-collector.<RELEASE_NAMESPACE>.svc:8080/metadata | jq

# TLS
curl -k -H "Authorization: Bearer <TOKEN>" https://<RELEAE_NAME>-cluster-collector.<RELEASE_NAMESPACE>.svc:8080/metadata | jq
```

As endpoints, instead of `/metadata`, feel free to also test `/container_metrics`, `/machine_sections`, etc.

Note that this will only work when disabling or adjusting the NetworkPolicies accordingly, as the `debug` pod won't be allowed to communicate with the cluster-collector having NetworkPolicies enabled in this chart.
