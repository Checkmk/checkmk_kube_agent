FROM gcr.io/cadvisor/cadvisor:v0.47.2 as release
ARG GIT_HASH
RUN sed -i -e 's/v3\.12/v3\.14/g' /etc/apk/repositories && \
    apk --no-cache upgrade --purge && \
    sed -i -e 's/v3\.14/v3\.15/g' /etc/apk/repositories && \
    apk --no-cache upgrade --purge && \
    rm -rf /tmp/* && \
    rm -rf /var/cache/apk/*
RUN echo "${GIT_HASH}" > GIT_HASH.txt
