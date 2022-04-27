ARG HADOLINT_VERSION="2.8.0"
ARG HELM_VERSION="3.8.1"
ARG TRIVY_VERSION="0.23.0"

ARG CHECKMK_AGENT_VERSION
FROM checkmk/check-mk-raw:"$CHECKMK_AGENT_VERSION" as checkmk

FROM python:3.10-alpine3.15 as base
# updating packages for security reasons
RUN apk add --no-cache expat=2.4.7-r0 libuuid=2.37.4-r0 coreutils=9.0-r2

FROM base as release
ARG CHECKMK_AGENT_VERSION
ARG GIT_HASH
ARG PROJECT_PYVERSION
ENV CHECKMK_AGENT_VERSION="${CHECKMK_AGENT_VERSION}"
COPY ./requirements_build.txt /tmp
COPY dist/checkmk_kube_agent-"$PROJECT_PYVERSION".tar.gz /tmp/
COPY --from=checkmk "/opt/omd/versions/${CHECKMK_AGENT_VERSION}.cre/share/check_mk/agents/check_mk_agent.openwrt" /usr/local/bin/check_mk_agent.openwrt
COPY docker/kubernetes-collector/wrapper.sh /usr/local/bin/check_mk_agent
RUN pip3 install --no-cache-dir -r /tmp/requirements_build.txt && \
    pip3 install --no-cache-dir /tmp/checkmk_kube_agent-"$PROJECT_PYVERSION".tar.gz && \
    sed -i "s/VERSION_CMK/$CHECKMK_AGENT_VERSION/" /usr/local/bin/check_mk_agent && \
    sed -i "s/VERSION_AGENT/$PROJECT_PYVERSION/" /usr/local/bin/check_mk_agent && \
    chmod +x /usr/local/bin/check_mk_agent && \
    addgroup appgroup -g 10001 && \
    adduser -HD appuser -G appgroup -u 10001 && \
    rm -rf /tmp/* && \
    rm -rf /var/cache/apk/*
RUN echo "${GIT_HASH}" > GIT_HASH.txt

FROM release as dev
ARG HADOLINT_VERSION
ARG HELM_VERSION
ARG TRIVY_VERSION
COPY ./requirements_dev.txt /tmp
RUN apk add --no-cache make=4.3-r0 && \
    pip install --no-cache-dir -r /tmp/requirements_dev.txt && \
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
