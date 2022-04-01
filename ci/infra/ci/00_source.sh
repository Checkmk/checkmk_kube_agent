export PM_PASS=$(pass pce-dev | sed -n "1 p")
export PM_USER=$(pass pce-dev | sed -n "2 p")@pve
export PRIVATE_KEY_PATH="$(pwd)/test@kube"
export CHECKMK_KUBE_AGENT_VERSION=$(date --iso)

export CONT_RUNTIME='docker' # or containerd
export KUBE_VERSION='1.23' # or 1.21 or 1.22

export CHECKMK_KUBE_AGENT_PATH="/home/bseidl/Code/checkmk_kube_agent"
export CHECKMK_KUBE_AGENT_DOCKER_VERSION="main_$(date '+%Y.%m.%d')"

export CHECKMK_PATH="/home/bseidl/Code/cmk/"
