FROM gcr.io/cadvisor/cadvisor:v0.43.0 as release
ARG PACKAGE_VERSION
COPY dist/checkmk_kube_agent-"$PACKAGE_VERSION".tar.gz /tmp/
COPY docker/node_collector/runscript.sh /usr/bin/checkmk-node-collector-runscript.sh
RUN sed -i -e 's/v3\.12/v3\.14/g' /etc/apk/repositories && \
    apk --no-cache upgrade --purge && \
    sed -i -e 's/v3\.14/v3\.15/g' /etc/apk/repositories && \
    apk --no-cache upgrade --purge && \
    apk add --no-cache python3=3.9.7-r4 && \
    python3 -m ensurepip && \
    pip3 install --no-cache-dir pip==21.3.1 setuptools==60.0.0 wheel==0.37.0 && \
    pip3 install --no-cache-dir /tmp/checkmk_kube_agent-"$PACKAGE_VERSION".tar.gz && \
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
    "https://github.com/aquasecurity/trivy/releases/download/v0.18.3/trivy_0.18.3_Linux-64bit.tar.gz" && \
    tar -xvzf trivy_0.18.3_Linux-64bit.tar.gz trivy && \
    mv trivy /usr/local/bin && \
    rm trivy_0.18.3_Linux-64bit.tar.gz && \
    wget -q \
    "https://github.com/instrumenta/kubeval/releases/latest/download/kubeval-linux-amd64.tar.gz" && \
    tar -xvzf kubeval-linux-amd64.tar.gz kubeval && \
    mv kubeval /usr/local/bin && \
    rm kubeval-linux-amd64.tar.gz && \
    pip3 install --no-cache-dir -r /tmp/requirements_dev.txt && \
    rm -rf /tmp/* && \
    rm -rf /var/cache/apk/*
ENTRYPOINT ["/bin/ash"]

FROM release
