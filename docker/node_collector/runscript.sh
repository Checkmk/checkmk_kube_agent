#!/bin/sh

# enable only cpu,memory
/usr/bin/cadvisor \
    --housekeeping_interval=30s \
    --max_housekeeping_interval=35s \
    --event_storage_event_limit=default=0 \
    --event_storage_age_limit=default=0 \
    --store_container_labels=false \
    --whitelisted_container_labels=io.kubernetes.container.name,io.kubernetes.pod.name,io.kubernetes.pod.namespace,io.kubernetes.pod.uid \
    --global_housekeeping_interval=30s \
    --event_storage_event_limit=default=0 \
    --event_storage_age_limit=default=0 \
    --disable_metrics=percpu,process,sched,tcp,udp,diskIO,disk,network \
    --allow_dynamic_housekeeping=true \
    --storage_duration=1m0s \
& /usr/bin/checkmk-node-collector "$@"
