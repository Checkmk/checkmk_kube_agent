# A minimal container to build the Python source and wheel package and Docker
# images to be used later on for testing and static code analysis

FROM docker:20.10.12-alpine3.15
RUN apk add python3=3.9.7-r4 make=4.3-r0 && \
    python3 -m ensurepip && \
    pip3 install --no-cache-dir pip==22.0.2 setuptools==60.7.0 wheel==0.37.1 && \
    rm -rf /tmp/* && \
    rm -rf /var/cache/apk/*
