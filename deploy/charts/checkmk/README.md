# checkmk

Installs the checkmk Kubernetes agent.

_Note: This chart is relatively young. Please use with care, read the documentation carefully, and file Pull Requests if required._

## Prerequisites

- Kubernetes 1.19+
- Helm 3+

<!-- ## Get Repo Info

```console
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
```

_See [helm repo](https://helm.sh/docs/helm/helm_repo/) for command documentation._ -->

## Install & Upgrade Chart

```console
# Helm
$ helm upgrade --install --create-namespace -n [RELEASE_NAMESPACE] [RELEASE_NAME] [-f values.yaml] .
```

Note that the flag `--create-namespace` will create the specified namespace `RELEASE_NAMESPACE` if it does not yet exists.

_See [configuration](#configuration) below._

_See [helm install](https://helm.sh/docs/helm/helm_install/) for command documentation._

## Uninstall Chart

```console
# Helm
$ helm uninstall -n [RELEASE_NAMESPACE] [RELEASE_NAME]
```

This removes all the Kubernetes components associated with the chart and deletes the release.

_See [helm uninstall](https://helm.sh/docs/helm/helm_uninstall/) for command documentation._

## Preview Helm changes

The [helm-diff](https://github.com/databus23/helm-diff) plugin gives us the possibility to preview what a `helm upgrade` would change.

Install it via `helm plugin install https://github.com/databus23/helm-diff`, then you can run the following prior to an install or upgrade command:

```console
# Helm (requires helm-diff plugin)
$ helm diff upgrade --install -n [RELEASE_NAMESPACE] [RELEASE_NAME] [-f values.yaml] .
```

## Render Helm templates

To render plain Kubernetes manifests from the Helm chart, run:

```console
# Helm
$ helm template -n [RELEASE_NAMESPACE] [RELEASE_NAME] .
```

Note that, as also with the other commands (except `helm uninstall`), you can speficy additional helm value files via `-f [MY_CUSTOM_VALUES_FILE]`, which configures the Helm chart using the custom configuration specified.

## Configuration

See [Customizing the Chart Before Installing](https://helm.sh/docs/intro/using_helm/#customizing-the-chart-before-installing). To see all configurable options with detailed comments:

```console
helm show values .
```

### Multiple releases

The same chart can be used to run multiple checkmk instances in the same cluster (or even the same namespace) if required. To achieve this, just rename the `RELEASE_NAME` when installing.

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