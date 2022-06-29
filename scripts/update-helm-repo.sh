#!/usr/bin/env sh

set -e

REPO_DIR="$(git rev-parse --show-toplevel)"
CURRENT_BRANCH="$(git branch --show-current)"

usage() {
    echo "Usage: --github-pages [GITHUB_PAGES_BRANCH] --helm-repo-index [HELM_REPO_INDEX_FILE] --url [KUBE_AGENT_GITHUB_URL] --version [RELEASE_VERSION]"
    echo "  github-pages            branch used to publish the helm repository on github"
    echo "  helm-repo-index         path to the helm repo index file"
    echo "  url                     url of the checkmk_kube_agent repository on github"
    echo "  version                 version that should be published"
}

while true; do
  case "$1" in
    -h | --help) break; usage;;
    -g | --github-pages) GITHUB_PAGES_BRANCH="$2"; shift 2;;
    -r | --helm-repo-index) HELM_REPO_INDEX_FILE="$2"; shift 2;;
    -u | --url) KUBE_AGENT_GITHUB_URL="$2"; shift 2;;
    -v | --version) VERSION="$2"; shift 2;;
    ?) usage;;
    --) shift; break ;;
    *) break ;;
  esac
done


if [ -z "${GITHUB_PAGES_BRANCH}" ] || [ -z "${HELM_REPO_INDEX_FILE}" ] || [ -z "${KUBE_AGENT_GITHUB_URL}" ] || [ -z "${VERSION}" ]; then
  usage
  exit 1
fi


git checkout "${GITHUB_PAGES_BRANCH}"
git pull
mv dist-helm/checkmk-kube-agent-helm-"${VERSION}".tgz "${REPO_DIR}"

merge_index_cmd=""
if [ -e "${HELM_REPO_INDEX_FILE}" ]; then
  merge_index_cmd="--merge ${HELM_REPO_INDEX_FILE}"
fi

helm repo index "${REPO_DIR}" "${merge_index_cmd}" --url "${KUBE_AGENT_GITHUB_URL}"/releases/download/v"${VERSION}"

git add "${HELM_REPO_INDEX_FILE}"
git commit "${HELM_REPO_INDEX_FILE}" -m "Add helm chart version ${VERSION}"
git push origin "${GITHUB_PAGES_BRANCH}"

git checkout "${CURRENT_BRANCH}"
