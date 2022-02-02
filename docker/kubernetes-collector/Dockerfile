ARG CHECKMK_AGENT_VERSION
FROM checkmk/check-mk-raw:"$CHECKMK_AGENT_VERSION" as checkmk

FROM python:3.10.2-alpine3.15 as release
ARG PACKAGE_VERSION
ARG CHECKMK_AGENT_VERSION
COPY dist/checkmk_kube_agent-"$PACKAGE_VERSION".tar.gz /tmp/
COPY --from=checkmk "/opt/omd/versions/${CHECKMK_AGENT_VERSION}.cre/share/check_mk/agents/check_mk_agent.openwrt" /usr/local/bin/check_mk_agent.openwrt
COPY docker/kubernetes-collector/wrapper.sh /usr/local/bin/check_mk_agent
RUN pip3 install --no-cache-dir pip==22.0.2 setuptools==60.7.0 wheel==0.37.1 && \
    pip3 install --no-cache-dir /tmp/checkmk_kube_agent-"$PACKAGE_VERSION".tar.gz && \
    addgroup appgroup -g 10001 && \
    adduser -HD appuser -G appgroup -u 10001 && \
    sed -i "s/VERSION_CMK/$CHECKMK_AGENT_VERSION/" /usr/local/bin/check_mk_agent && \
    sed -i "s/VERSION_AGENT/$PACKAGE_VERSION/" /usr/local/bin/check_mk_agent && \
    chmod +x /usr/local/bin/check_mk_agent && \
    rm -rf /tmp/* && \
    rm -rf /var/cache/apk/*

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
    "https://github.com/instrumenta/kubeval/releases/download/v0.16.1/kubeval-linux-amd64.tar.gz" && \
    tar -xvzf kubeval-linux-amd64.tar.gz kubeval && \
    mv kubeval /usr/local/bin && \
    rm kubeval-linux-amd64.tar.gz && \
    pip install --no-cache-dir -r /tmp/requirements_dev.txt && \
    rm -rf /tmp/* && \
    rm -rf /var/cache/apk/*
ENTRYPOINT ["/bin/ash"]

FROM release
USER appuser
