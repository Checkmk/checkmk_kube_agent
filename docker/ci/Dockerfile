# A minimal container to build the Python source and wheel package and Docker
# images to be used later on for testing and static code analysis


FROM docker:20.10.12-alpine3.15
ARG HELM_VERSION="3.8.2"
# Notes on "gh" tool in combination with the "gh release create" command:
# --target: in theory it should be possible to use a tag instead of a commit sha, but this does not work currently
# --notes: must be set (even if it's left blank), otherwise it does not work properly
# --title: should be set, otherwise the commit message of the last commit is used
ARG GH_VERSION="2.8.0"
COPY requirements_build.txt /tmp/
RUN apk add python3=3.9.7-r4 make=4.3-r0 git=2.34.2-r0 && \
    wget -q "https://get.helm.sh/helm-v${HELM_VERSION}-linux-amd64.tar.gz" && \
    tar -xvzf helm-v${HELM_VERSION}-linux-amd64.tar.gz linux-amd64/helm --strip-components 1 -C /usr/local/bin && \
    rm -rf helm-v${HELM_VERSION}-linux-amd64.tar.gz && \
    wget -q "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_amd64.tar.gz" && \
    tar -xvzf gh_${GH_VERSION}_linux_amd64.tar.gz gh_${GH_VERSION}_linux_amd64/bin/gh --strip-components 2 -C /usr/local/bin && \
    rm -rf gh_${GH_VERSION}_linux_amd64.tar.gz && \
    python3 -m ensurepip && \
    pip3 install --no-cache-dir -r /tmp/requirements_build.txt && \
    rm -rf /tmp/* && \
    rm -rf /var/cache/apk/*

RUN addgroup -g 1000 jenkins && adduser -u 1001 -G jenkins -s /bin/ash jenkins -D
