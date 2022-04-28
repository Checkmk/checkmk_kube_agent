#!/usr/bin/env sh
set -e

VERSION=$1
METHOD=$2
BRANCH=$3

TAG_NAME="v${VERSION}"

case $METHOD in
  rebuild_version)
    # Only switch to the exisiting tag and expect it to exist
    git checkout "${TAG_NAME}"
    ;;

  minor | patch | beta | finalize_version)
    # Create set version commit and switch to a new branch
    git fetch --prune --prune-tags
    git checkout ${BRANCH}
    git pull --rebase
    NEW_VERSION=${VERSION} make setversion;
    git commit -am "Set version to ${VERSION}"
    git tag ${TAG_NAME}
    git push --tags origin ${BRANCH}
    ;;

  *)
    echo -n "Unsupported method: ${METHOD}"
    exit 1
    ;;
esac
