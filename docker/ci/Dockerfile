# A container to build the Python source and wheel package and Docker
# images to be used later on for testing and static code analysis

FROM python:3.10-alpine3.15 
ARG HELM_VERSION="3.8.2"
# Notes on "gh" tool in combination with the "gh release create" command:
# --target: in theory it should be possible to use a tag instead of a commit sha, but this does not work currently
# --notes: must be set (even if it's left blank), otherwise it does not work properly
# --title: should be set, otherwise the commit message of the last commit is used
ARG GH_VERSION="2.8.0"
COPY requirements_build.txt /tmp/
COPY ci/infra/ansible/requirements.* /tmp/
RUN apk add make git docker terraform openssh && \
    apk add --no-cache gcc libffi-dev musl-dev -t build-deps && \
    wget -q "https://get.helm.sh/helm-v${HELM_VERSION}-linux-amd64.tar.gz" && \
    tar -xvzf helm-v${HELM_VERSION}-linux-amd64.tar.gz linux-amd64/helm --strip-components 1 -C /usr/local/bin && \
    rm -rf helm-v${HELM_VERSION}-linux-amd64.tar.gz && \
    wget -q "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_amd64.tar.gz" && \
    tar -xvzf gh_${GH_VERSION}_linux_amd64.tar.gz gh_${GH_VERSION}_linux_amd64/bin/gh --strip-components 2 -C /usr/local/bin && \
    rm -rf gh_${GH_VERSION}_linux_amd64.tar.gz && \
    pip3 install --no-cache-dir -r /tmp/requirements_build.txt -r /tmp/requirements.txt && \
    ansible-galaxy install --roles-path /etc/ansible/roles -r /tmp/requirements.yml && \
    apk del build-deps && \
    rm -rf /tmp/* && \
    rm -rf /var/cache/apk/*

RUN addgroup -g 1000 jenkins && adduser -u 1001 -G jenkins -s /bin/ash jenkins -D
