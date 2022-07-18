# Purpose

This directory contains ansible playbooks to automate the creation and management of VMs on Proxmox that make up a Kubernetes cluster.
The version of the Kubernetes cluster as well as the container runtime are configurable.
Possible configuration options are provided by `inventory/hosts.ini`.

# Prerequisites

* Python3
* Connection properties provided as environment variables, see `inventory/group_vars/all/ansible.yml`

# Scope

The playbooks are able to perform the following tasks:
* Management of VMs:
  * create
  * destroy
  * stop
  * start
  * snapshot
* Provisioning to VMs:
  * container runtime
  * Kubernetes

# Usage

`run_hosts` must always be specified and should correspond to the Kubernetes version and container runtime that should be managed.

## Deploy

```console
ansible-playbook --inventory inventory/hosts.ini playbooks/deploy.yml --extra-vars "run_hosts=k8s_121_containerd"
```

## Destroy

```console
ansible-playbook --inventory inventory/hosts.ini playbooks/destroy.yml --extra-vars "run_hosts=k8s_121_containerd"
```

## Manage

```console
ansible-playbook --inventory inventory/hosts.ini playbooks/manage.yml --extra-vars "run_hosts=k8s_121_containerd target_state=started"
```

```console
ansible-playbook --inventory inventory/hosts.ini playbooks/manage.yml --extra-vars "run_hosts=k8s_121_containerd target_state=stopped"
```

```console
ansible-playbook --inventory inventory/hosts.ini playbooks/manage.yml --extra-vars "run_hosts=k8s_121_containerd target_state=restarted"
```

## Snapshots

The name of the snapshot can be chosen freely.
The snapshot state is fixed.

### Create

```console
ansible-playbook --inventory inventory/hosts.ini playbooks/snapshot.yml --extra-vars "run_hosts=k8s_121_containerd snap_state=present snap_name=snappy"
```

### Roll back to

```console
ansible-playbook --inventory inventory/hosts.ini playbooks/snapshot.yml --extra-vars "run_hosts=k8s_121_containerd snap_state=rollback snap_name=snappy"
```

### Delete

```console
ansible-playbook --inventory inventory/hosts.ini playbooks/snapshot.yml --extra-vars "run_hosts=k8s_121_containerd snap_state=absent snap_name=snappy"
```

## Provision container runtime and Kubernetes

```console
ansible-playbook --inventory inventory/hosts.ini playbooks/provision.yml --extra-vars "run_hosts=k8s_121_containerd"
```
