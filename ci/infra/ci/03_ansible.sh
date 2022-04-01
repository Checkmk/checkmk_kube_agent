# prepare kubernetes files

set -e
current=$(pwd)

cd "$CHECKMK_KUBE_AGENT_PATH"
cd deploy/kubernetes

git checkout .
sed -i "s/main_<YYYY.MM.DD>/$CHECKMK_KUBE_AGENT_DOCKER_VERSION/" cluster-collector.yaml
sed -i "s/main_<YYYY.MM.DD>/$CHECKMK_KUBE_AGENT_DOCKER_VERSION/" node-collector.yaml
sed -i "s/main_<YYYY.MM.DD>/$CHECKMK_KUBE_AGENT_DOCKER_VERSION/" node-collector-cadvisor.yaml
sed -i '/--verify-ssl/d' cluster-collector.yaml
sed -i '/--verify-ssl/d' node-collector.yaml
# hack to get colors, but no pager. otherwise you will have to exit the pager to go on...
git diff --color=always | cat

cd "$current/ansible"
ansible-playbook -u test -i inventory/hosts playbooks/provision.yml -e "kubernetes_version=${KUBE_VERSION} container_runtime=${CONT_RUNTIME} checkmk_kube_agent_path=${CHECKMK_KUBE_AGENT_PATH}" --tags "common,${CONT_RUNTIME}" --private-key "$PRIVATE_KEY_PATH"
