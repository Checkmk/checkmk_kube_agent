#!/usr/bin/env bash

set -e

VERSION=$1
METHOD=$2

case $METHOD in
  rebuild_version)
    # Only switch to the exisiting tag and expect it to exist
    git checkout ${VERSION}
    ;;

  minor | patch)
    # Create set version commit and switch to a new branch
    NEW_VERSION=${VERSION} make setversion;
    git tag ${VERSION}
    git commit -am "Set version to ${VERSION}"
    git pull --tags origin main
    git push --tags origin main
    ;;

  *)
    echo -n "Unsupported method: ${METHOD}"
    exit 1
    ;;
esac
