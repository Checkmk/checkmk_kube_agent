ARG HADOLINT_VERSION="2.8.0"
ARG HELM_VERSION="3.8.1"
ARG TRIVY_VERSION="0.23.0"

ARG CHECKMK_AGENT_VERSION
FROM checkmk/check-mk-raw:"$CHECKMK_AGENT_VERSION" AS checkmk

FROM artifacts.lan.tribe29.com:4000/python:3.10-alpine3.15 AS base
# pciutils is used by mk_inventory.linux
# coreutils is needed for the Checkmk agent to run properly
# hadolint ignore=DL3018
RUN apk update && apk add --no-cache coreutils pciutils

FROM base AS builder
ARG CHECKMK_AGENT_VERSION
ARG PROJECT_PYVERSION
ARG CHECKMK_AGENT_DIR="/opt/omd/versions/default/share/check_mk/agents"
ARG CHECKMK_AGENT_PLUGIN_DIR="${CHECKMK_AGENT_DIR}/plugins"
COPY ./requirements_build.txt /tmp
COPY dist/checkmk_kube_agent-"${PROJECT_PYVERSION}".tar.gz /tmp/
COPY --from=checkmk "${CHECKMK_AGENT_DIR}/check_mk_agent.openwrt" /install/bin/check_mk_agent.openwrt
COPY --from=checkmk "${CHECKMK_AGENT_PLUGIN_DIR}/mk_inventory.linux" /install/bin/mk_inventory.linux
COPY --from=checkmk "${CHECKMK_AGENT_PLUGIN_DIR}/lnx_container_host_if.linux" /install/bin/lnx_container_host_if.linux
COPY docker/kubernetes-collector/wrapper.sh /install/bin/check_mk_agent
RUN pip3 install --no-cache-dir -r /tmp/requirements_build.txt && \
    pip3 install --no-cache-dir --prefix=/install /tmp/checkmk_kube_agent-"$PROJECT_PYVERSION".tar.gz && \
    sed -i "s/VERSION_CMK/${CHECKMK_AGENT_VERSION}/" /install/bin/check_mk_agent && \
    sed -i "s/VERSION_AGENT/${PROJECT_PYVERSION}/" /install/bin/check_mk_agent && \
    chmod +x /install/bin/check_mk_agent && \
    rm -rf /tmp/* && \
    rm -rf /var/cache/apk/*

FROM base AS release
ARG CHECKMK_AGENT_VERSION
ARG GIT_HASH
ENV CHECKMK_AGENT_VERSION="${CHECKMK_AGENT_VERSION}"
COPY --from=builder /install /usr/local
RUN addgroup appgroup -g 10001 && \
    adduser -HD appuser -G appgroup -u 10001
RUN echo "${GIT_HASH}" > GIT_HASH.txt

FROM release AS dev
ARG HADOLINT_VERSION
ARG HELM_VERSION
ARG TRIVY_VERSION
COPY ./requirements_dev.txt /tmp
COPY ./requirements_test.txt /tmp
RUN apk add --no-cache make=4.3-r0 && \
    pip install --no-cache-dir -r /tmp/requirements_dev.txt -r /tmp/requirements_test.txt && \
    wget -q \
    "https://github.com/hadolint/hadolint/releases/download/v${HADOLINT_VERSION}/hadolint-Linux-x86_64" && \
    mv hadolint-Linux-x86_64 /usr/local/bin/hadolint &&\
    chmod +x /usr/local/bin/hadolint && \
    wget -q \
    "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_Linux-64bit.tar.gz" && \
    tar -xvzf trivy_${TRIVY_VERSION}_Linux-64bit.tar.gz trivy && \
    mv trivy /usr/local/bin && \
    rm trivy_${TRIVY_VERSION}_Linux-64bit.tar.gz && \
    wget -q \
    "https://get.helm.sh/helm-v${HELM_VERSION}-linux-amd64.tar.gz" && \
    tar -xvzf helm-v${HELM_VERSION}-linux-amd64.tar.gz linux-amd64/helm --strip-components 1 && \
    mv helm /usr/local/bin && \
    rm helm-v${HELM_VERSION}-linux-amd64.tar.gz && \
    rm -rf /tmp/* && \
    rm -rf /var/cache/apk/*
ENTRYPOINT ["/bin/ash"]

FROM release
USER appuser
