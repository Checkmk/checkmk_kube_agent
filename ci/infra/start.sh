#!/usr/bin/env bash
#
# Written by: Robin Gierse - robin.gierse@tribe29.com - on 20220103
#
# Purpose:
# This script bootstraps the kubernetes testing environments.
#
# Usage:
# ./start.sh -m $MODE -k $KUBE_VERSION -r $CONT_RUNTIME

set -e

while getopts "m:k:r:" arg; do
  case $arg in
    m)
      MODE=$OPTARG
    ;;
    k)
      KUBE_VERSION=$OPTARG
    ;;
    r)
      CONT_RUNTIME=$OPTARG
    ;;
    *)
      echo 'Unknown parameter, numbnut!'
    ;;
  esac
done

# Necessary for pip installed tools in ~/.local/bin/
export PATH="${PATH}:${HOME}/.local/bin/"

# ToDo: Implement value verification
# VALID_CONT_RUNTIMES='docker containerd'
# VALID_KUBE_VERSIONS='1.21 1.22 1.23'

EXE_PIP="$(command -v pip)"
EXE_TERRAFORM="$(command -v terraform)"
EXE_ANSIBLE_PLAYBOOK="$(command -v ansible-playbook)"
EXE_ANSIBLE_GALAXY="$(command -v ansible-galaxy)"

# ToDo:
# vim ~/.ssh/config:
#   Host 10.200.3.*
#       StrictHostKeyChecking false
#       UserKnownHostsFile /dev/null
#
# export PM_USER='$USER' && export PM_PASS='$SECRET'

_validate() {
  if [ -z "${PM_USER}" ] ; then
    echo 'No Proxmox User set! Use <PM_USER>.' ; exit 1
  fi
  if [ -z "${PM_PASS}" ] ; then
    echo 'No Proxmox password set! Use <PM_PASS>!' ; exit 1
  fi
  if [ -z "${EXE_PIP}" ] ; then
    echo 'No pip found on your system! Please install it prior to using this script.' ; exit 1
  fi
  if [ -z "${EXE_TERRAFORM}" ] ; then
    echo 'No terraform found on your system! Please install it prior to using this script.' ; exit 1
  fi
}

_init() {
    cd ./terraform || exit 1
    ${EXE_TERRAFORM} init
    cd ../ansible || exit 1
    ${EXE_PIP} install -r requirements.txt
    ${EXE_ANSIBLE_GALAXY} install -r requirements.yml
    ${EXE_ANSIBLE_GALAXY} collection install -r requirements.yml
    cd .. || exit 1
}

_start() {
    cd ./terraform || exit 1
    ${EXE_TERRAFORM} plan -out plan
    ${EXE_TERRAFORM} apply -auto-approve plan
    cd ../ansible || exit 1
    sleep 15  # There seems to be an issue where APT is still locked after terraform finished
    ${EXE_ANSIBLE_PLAYBOOK} -u test -i inventory/hosts playbooks/provision.yml -e "kubernetes_version=${KUBE_VERSION} container_runtime=${CONT_RUNTIME}" --tags "common,${CONT_RUNTIME}"
    cd .. || exit 1
}

_destroy() {
    cd ./terraform || exit 1
    ${EXE_TERRAFORM} destroy -auto-approve
    cd .. || exit 1
}

# Main

_validate

case $MODE in
  init)
    _init
    ;;
  start)
    _start
    ;;
  destroy)
    _destroy
    ;;
  *)
    echo 'Wrong mode, bro!'
    ;;
esac
