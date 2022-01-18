FROM python:3.9.9-alpine3.14 as release
ARG PACKAGE_VERSION
COPY dist/checkmk_kube_agent-"$PACKAGE_VERSION".tar.gz /tmp/
RUN pip3 install --no-cache-dir pip==21.3.1 setuptools==60.0.0 wheel==0.37.0 && \
    pip3 install --no-cache-dir /tmp/checkmk_kube_agent-"$PACKAGE_VERSION".tar.gz && \
    addgroup appgroup -g 10001 && \
    adduser -HD appuser -G appgroup -u 10001 && \
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
    pip install --no-cache-dir -r /tmp/requirements_dev.txt && \
    rm -rf /tmp/* && \
    rm -rf /var/cache/apk/*
ENTRYPOINT ["/bin/ash"]

FROM release
USER appuser
