#!/usr/bin/env bash

set -e

VERSION=$1
METHOD=$2
BRANCH=main

case $METHOD in
  rebuild_version)
    # Only switch to the exisiting tag and expect it to exist
    git checkout ${VERSION}
    ;;

  minor | patch)
    # Create set version commit and switch to a new branch
    git checkout ${BRANCH}
    git pull --rebase
    NEW_VERSION=${VERSION} make setversion;
    git commit -am "Set version to ${VERSION}"
    git tag ${VERSION}
    git pull --tags origin ${BRANCH}
    git push --tags origin ${BRANCH}
    ;;

  *)
    echo -n "Unsupported method: ${METHOD}"
    exit 1
    ;;
esac
