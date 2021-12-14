# A minimal container to build the Python source and wheel package and Docker
# images to be used later on for testing and static code analysis

FROM docker:20.10.12-alpine3.14
RUN apk add python3=3.9.5-r2 make=4.3-r0 && \
    python3 -m ensurepip && \
    pip3 install --no-cache-dir pip==21.3.1 setuptools==60.0.0 wheel==0.37.0 && \
    rm -rf /tmp/* && \
    rm -rf /var/cache/apk/*
