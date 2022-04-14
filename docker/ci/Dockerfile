# A minimal container to build the Python source and wheel package and Docker
# images to be used later on for testing and static code analysis


FROM docker:20.10.12-alpine3.15
ARG HELM_VERSION="3.8.2"
RUN apk add python3=3.9.7-r4 make=4.3-r0 git=2.34.2-r0 && \
    wget -q "https://get.helm.sh/helm-v${HELM_VERSION}-linux-amd64.tar.gz" && \
    tar -xvzf helm-v${HELM_VERSION}-linux-amd64.tar.gz linux-amd64/helm --strip-components 1 -C /usr/local/bin && \
    rm -rf helm-v${HELM_VERSION}-linux-amd64.tar.gz && \
    python3 -m ensurepip && \
    pip3 install --no-cache-dir pip==22.0.2 setuptools==60.7.0 wheel==0.37.0 semver==2.13.0 packaging==21.3 &&  \
    rm -rf /tmp/* && \
    rm -rf /var/cache/apk/*

RUN addgroup -g 1000 jenkins && adduser -u 1001 -G jenkins -s /bin/ash jenkins -D
