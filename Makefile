VERSION := ""

helm:
	wget https://github.com/Checkmk/checkmk_kube_agent/releases/download/v$(VERSION)/checkmk-kube-agent-helm-$(VERSION).tgz
	helm repo index . --merge index.yaml --url "https://github.com/checkmk/checkmk_kube_agent/releases/download/v$(VERSION)"
	rm checkmk-kube-agent-helm-$(VERSION).tgz
	git diff
