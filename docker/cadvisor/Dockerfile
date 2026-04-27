FROM artifacts.lan.tribe29.com:4000/cadvisor:0.56.2 AS release
ARG GIT_HASH
RUN apk --no-cache upgrade --purge && \
    rm -rf /tmp/* && \
    rm -rf /var/cache/apk/*
RUN echo "${GIT_HASH}" > GIT_HASH.txt
