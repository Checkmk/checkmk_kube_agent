# A minimal container to build the Python source and wheel package and Docker
# images to be used later on for testing and static code analysis

FROM docker:20.10
RUN apk add python3 make && \
    python3 -m ensurepip && \
    pip3 install setuptools wheel && \
    rm -rf /tmp/* && \
    rm -rf /var/cache/apk/*
