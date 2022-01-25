FROM gcr.io/cadvisor/cadvisor:v0.43.0 as release
RUN sed -i -e 's/v3\.12/v3\.14/g' /etc/apk/repositories && \
    apk --no-cache upgrade --purge && \
    sed -i -e 's/v3\.14/v3\.15/g' /etc/apk/repositories && \
    apk --no-cache upgrade --purge && \
    rm -rf /tmp/* && \
    rm -rf /var/cache/apk/*
