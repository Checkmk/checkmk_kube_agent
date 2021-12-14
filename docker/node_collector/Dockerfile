FROM gcr.io/cadvisor/cadvisor:v0.43.0 as release
ARG PACKAGE_VERSION
COPY dist/checkmk_kube_agent-"$PACKAGE_VERSION".tar.gz /tmp/
RUN sed -i -e 's/v3\.12/v3\.14/g' /etc/apk/repositories && \
    apk upgrade --purge && \
    apk add --no-cache python3 && \
    python3 -m ensurepip && \
    pip3 install --no-cache-dir /tmp/checkmk_kube_agent-"$PACKAGE_VERSION".tar.gz && \
    rm -rf /tmp/* && \
    rm -rf /var/cache/apk/*

FROM release as dev
COPY ./requirements_dev.txt /tmp
RUN apk add --no-cache make && \
    pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r /tmp/requirements_dev.txt && \
    rm -rf /tmp/* && \
    rm -rf /var/cache/apk/*
ENTRYPOINT ["/bin/ash"]

FROM release
