# checkmk

Installs the checkmk Kubernetes agent.

_Note: This chart is currently work-in-progress. Please use with care, read the documentation carefully, and file Pull Requests if needed._

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