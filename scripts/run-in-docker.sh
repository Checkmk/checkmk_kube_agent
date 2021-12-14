#!/usr/bin/env sh

set -e

REPO_DIR="$(git rev-parse --show-toplevel)"

usage() {
    echo "Usage: --image [IMAGE_ID] --command [COMMAND]"
    echo "  image            Docker image ID or name to be used to create the container"
    echo "  command          command to be executed inside the container"
}

while true; do
  case "$1" in
    -h | --help) break; usage;;
    -i | --image) IMAGE_ID="$2"; shift 2;;
    -c | --command) COMMAND="$2"; shift 2;;
    ?) usage;;
    --) shift; break ;;
    *) break ;;
  esac
done

if [ -z "${IMAGE_ID}" ] || [ -z "${COMMAND}" ]; then
    usage
    exit 1
fi

echo "Running in Docker container from image ${IMAGE_ID} (workdir=${REPO_DIR})"

docker run -t -a stdout -a stderr \
    --rm \
    --init \
    -u "$(id -u):$(id -g)" \
    -v "${REPO_DIR}:${REPO_DIR}" \
    -w "${REPO_DIR}" \
    --env XDG_CACHE_HOME="/tmp/.cache" \
    --entrypoint="/bin/ash" \
    "${IMAGE_ID}" \
    -c "${COMMAND}"
