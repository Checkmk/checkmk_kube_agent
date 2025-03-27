FROM artifacts.lan.tribe29.com:4000/python:3.10-alpine3.15 as base

FROM base as common
ARG HELM_VERSION="3.8.2"
# make: run targets that build Python source/wheel packages
# git: ensure a clean repo state
# openssh: release: ssh to push to git/github
#          integratin test: ssh to connect to VMs via ansible
# docker: build release image, docker login for integration test
# hadolint ignore=DL3018
RUN apk add --no-cache make git openssh docker=~20.10 && \
    wget -q "https://get.helm.sh/helm-v${HELM_VERSION}-linux-amd64.tar.gz" && \
    tar -xvzf helm-v${HELM_VERSION}-linux-amd64.tar.gz linux-amd64/helm --strip-components 1 -C /usr/local/bin && \
    rm -rf helm-v${HELM_VERSION}-linux-amd64.tar.gz && \
    rm -rf /tmp/* && \
    rm -rf /var/cache/apk/*
RUN addgroup -g 1000 jenkins && adduser -u 1001 -G jenkins -s /bin/ash jenkins -D

FROM common as releaser
ARG GH_VERSION="2.8.0"
COPY requirements_build.txt /tmp/
# Notes on "gh" tool in combination with the "gh release create" command:
# --target: in theory it should be possible to use a tag instead of a commit sha, but this does not work currently
# --notes: must be set (even if it's left blank), otherwise it does not work properly
# --title: should be set, otherwise the commit message of the last commit is used
RUN wget -q "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_amd64.tar.gz" && \
    tar -xvzf gh_${GH_VERSION}_linux_amd64.tar.gz gh_${GH_VERSION}_linux_amd64/bin/gh --strip-components 2 -C /usr/local/bin && \
    rm -rf gh_${GH_VERSION}_linux_amd64.tar.gz && \
    pip3 install --no-cache-dir -r /tmp/requirements_build.txt && \
    rm -rf /tmp/* && \
    rm -rf /var/cache/apk/*

FROM common as integration-tester
ARG KUBECTL_VERSION="v1.24.3"
COPY requirements_test.txt /tmp/
COPY ci/integration/ansible/requirements.* /tmp/
COPY ci/integration/ansible/ansible.cfg /etc/ansible/ansible.cfg
# build-deps: build dependencies of ansible
# coreutils: base64 decoder to decode tokens/CA certs from the K8s cluster
# hadolint ignore=DL3018
RUN apk add --no-cache coreutils && \
    apk add --no-cache gcc libffi-dev musl-dev -t build-deps && \
    wget -q "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" && \
    chmod +x kubectl && mv kubectl /usr/local/bin && \
    pip3 install --no-cache-dir -r /tmp/requirements.txt -r /tmp/requirements_test.txt && \
    apk del build-deps && \
    mkdir -p /etc/ansible/roles && mkdir -p /etc/ansible/collections && \
    ansible-galaxy install --roles-path /etc/ansible/roles -r /tmp/requirements.yml && \
    ansible-galaxy collection install -r /tmp/requirements.yml && \
    rm -rf /tmp/* && \
    rm -rf /var/cache/apk/*

FROM releaser
