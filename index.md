# Checkmk Kube Agent Repository

![Checkmk](https://checkmk.com/application/files/thumbnails/low_res/7015/9834/3137/checkmk_logo_main.png)

## Add the helm repository

```sh
helm repo add [REPO] https://tribe29.github.io/checkmk_kube_agent
```

Example:
```sh
helm repo add myrepo https://tribe29.github.io/checkmk_kube_agent
```

## Install the latest stable Checkmk collectors

```sh
helm upgrade --install --create-namespace -n [NAMESPACE] [RELEASE] [REPO]/checkmk
```

Example:
```sh
helm upgrade --install --create-namespace -n checkmk-monitoring checkmk myrepo/checkmk
```

For more details on the installation please see the [chart's README](https://github.com/tribe29/checkmk_kube_agent/blob/main/deploy/charts/checkmk/README.md).

## License

[Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0)
