ARG CHECKMK_AGENT_VERSION
FROM checkmk/check-mk-raw:"$CHECKMK_AGENT_VERSION" as checkmk

FROM python:3.10.2-alpine3.15 as release
ARG PROJECT_PYVERSION
ARG CHECKMK_AGENT_VERSION
ARG GIT_HASH
ENV CHECKMK_AGENT_VERSION="${CHECKMK_AGENT_VERSION}"
COPY dist/checkmk_kube_agent-"$PROJECT_PYVERSION".tar.gz /tmp/
COPY --from=checkmk "/opt/omd/versions/${CHECKMK_AGENT_VERSION}.cre/share/check_mk/agents/check_mk_agent.openwrt" /usr/local/bin/check_mk_agent.openwrt
COPY docker/kubernetes-collector/wrapper.sh /usr/local/bin/check_mk_agent
RUN apk add --no-cache expat=2.4.7-r0 libuuid=2.37.4-r0 coreutils=9.0-r2  && \
    pip3 install --no-cache-dir pip==22.0.3 setuptools==60.9.3 wheel==0.37.1 && \
    pip3 install --no-cache-dir /tmp/checkmk_kube_agent-"$PROJECT_PYVERSION".tar.gz && \
    addgroup appgroup -g 10001 && \
    adduser -HD appuser -G appgroup -u 10001 && \
    sed -i "s/VERSION_CMK/$CHECKMK_AGENT_VERSION/" /usr/local/bin/check_mk_agent && \
    sed -i "s/VERSION_AGENT/$PROJECT_PYVERSION/" /usr/local/bin/check_mk_agent && \
    chmod +x /usr/local/bin/check_mk_agent && \
    rm -rf /tmp/* && \
    rm -rf /var/cache/apk/*
RUN echo "${GIT_HASH}" > GIT_HASH.txt

FROM release as dev
COPY ./requirements_dev.txt /tmp
RUN apk add --no-cache make=4.3-r0 && \
    wget -q \
    "https://github.com/hadolint/hadolint/releases/download/v2.8.0/hadolint-Linux-x86_64" && \
    mv hadolint-Linux-x86_64 /usr/local/bin/hadolint &&\
    chmod +x /usr/local/bin/hadolint && \
    wget -q \
    "https://github.com/aquasecurity/trivy/releases/download/v0.23.0/trivy_0.23.0_Linux-64bit.tar.gz" && \
    tar -xvzf trivy_0.23.0_Linux-64bit.tar.gz trivy && \
    mv trivy /usr/local/bin && \
    rm trivy_0.23.0_Linux-64bit.tar.gz && \
    wget -q \
    "https://get.helm.sh/helm-v3.8.1-linux-amd64.tar.gz" && \
    tar -xvzf helm-v3.8.1-linux-amd64.tar.gz linux-amd64/helm --strip-components 1 && \
    mv helm /usr/local/bin && \
    rm helm-v3.8.1-linux-amd64.tar.gz && \
    pip install --no-cache-dir -r /tmp/requirements_dev.txt && \
    rm -rf /tmp/* && \
    rm -rf /var/cache/apk/*
ENTRYPOINT ["/bin/ash"]

FROM release
USER appuser
