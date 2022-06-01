# Kubernetes Testing Suite

## Proxmox

### Before we start

You will need:
- Your favorite Ansible person
- Instead of the person make sure Ansible is installed properly
  - Ansible: Will be installed through `requirements.txt`
    (If you need to install it manually, do: `pip install ansible`)
- The user and password for authentication against the compute provider of choice
  - For Proxmox: Search for 'kubernetes-tests' in TeamPass

### Getting started

Export the necessary environment variables (the 'kubernetes-tests' user):

    export PM_USER='$USER' && \                                             
    export PM_PASS='$PASS' && \
    export PM_NODE='$NODE' && \
    export PM_HOST='$NODE.$DOMAIN' && \
    export PM_URL='https://$HOST:8006'

Now move to the ansible directory and install the prerequisites:

    cd ./ansible
    ansible-galaxy install -r requirements.yml
    pip install -r requirements.txt

Now you can run the playbooks. The following are examples,
that point out the general apporach. Make sure to adapt the commands properly!

    ansible-playbook -i inventory/hosts.ini playbooks/deploy.yml -e "run_hosts=kubernetes"

Deploy the machines denoted by `run_hosts`.

    ansible-playbook -i inventory/hosts.ini playbooks/manage.yml -e "run_hosts=kubernetes target_state=started"

Start, stop and restart the machined denoted by `run_hosts`. Possible values of `target_state` are:

---
- started
- stopped
- restarted
---

    ansible-playbook -i inventory/hosts.ini playbooks/provision.yml -e "run_hosts=kubernetes"

Provision the machines denoted by `run_hosts` with Kubernetes.

    ansible-playbook -i inventory/hosts.ini playbooks/snapshot.yml -e "run_hosts=kubernetes snap_state=present snap_name=Testing"

Manage snapshots on the machined denoted by `run_hosts`. `snap_name` can be chosen freely but should be understandable.
Possible values of `snap_state` are:

---
- present
- absent
- rollback
---
    ansible-playbook -i inventory/hosts.ini playbooks/auth.yml -e "run_hosts=kubernetes"

Collect kube config file from masters to be used on the Ansible control node.

    ansible-playbook -i inventory/hosts.ini playbooks/destroy.yml -e "run_hosts=kubernetes"

Destroy all machined denoted by `run_hosts`.
