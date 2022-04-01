# Kubernetes Testing Suite

## Proxmox

### Before we start

You will need:
- Your favorite Ansible and Terraform dude
- Instead of the dude make sure Ansible and Terraform are installed properly
  - Terraform: https://wiki.lan.tribe29.com/books/robins-book-chh/page/terraform
  - Ansible: Will be installed through `requirements.txt`
    (If you need to install it manually, do: `pip install ansible`)
- The user and password for authentication against the compute provider of choice
  - For Proxmox: Search for 'kubernetes-tests' in TeamPass

### Getting started

Configure SSH, so it will not complain about untrusted keys. Add the following snippet to your `~/.ssh/config`:

    Host 10.200.3.*
        StrictHostKeyChecking false
        UserKnownHostsFile /dev/null

Next export the necessary environment variables (the 'kubernetes-tests' user):

    export PM_USER='$USER' && export PM_PASS='$SECRET'

*Hint: There is a script ins this folder, which will help you use the configuration.*
*However: Be sure to understand what is going on, before using the script!*
*The file is named: `start.sh`. See the script header for usage information.*

Go to the terraform directory and deploy the VMs (this may take a few minutes):

    cd ./terraform
    terraform init
    terraform plan -out plan
    terraform apply -auto-approve plan

Once these commands have exited successfully provision the VMs with Kubernetes.
To do this you need to choose which Kubernetes version and container runtime you want to use.
Valid options for container $RUNTIMES are:
- docker
- containerd

Now move to the ansible directory, install prerequisites
and provision the VMs (this may take a few minutes):

    cd ./ansible
    ansible-galaxy install -r requirements.yml
    pip install -r requirements.txt
    
    ansible-playbook -u test -i inventory/hosts playbooks/provision.yml -e "kubernetes_version=1.21" --tags $RUNTIME

After you are done with you tests, destroy the VMs:    
    
    cd ./terraform
    terraform destroy -auto-approve

That wraps it up.

## AWS EKS
TBD

## Notes
- Tests sequentially (3 machines at once, combinations after one another), or parallel (3 machines times X combinations at the same time)? -> Parallel! As much as possible! That would be 18 hosts (3 per cluster x 3 kube versions x 2 runtimes), how to create proper batches? -> Sequencially is fine for now!

- Interfaces for information exchange? e.g. hostnames, URLs etc.? Specifically: Kubernetes Auth (Certs)?
    - Write ini-style config file from ansible for tests -> POC done, details need clarification

- Where to store this repo? -> Lisa
