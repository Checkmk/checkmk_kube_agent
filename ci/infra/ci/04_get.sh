set -e
export PIPENV_IGNORE_VIRTUALENVS=1

TOKEN=$(cat /tmp/token)

cd "$CHECKMK_PATH"

pipenv run python3 -m cmk.special_agents.agent_kube \
  --debug \
  --token "$TOKEN" \
  --cluster integrationtest \
  --api-server-endpoint https://kubernetes-tests-master.dev.tribe29.com:6443 \
  --cluster-collector-endpoint https://kubernetes-tests-node1.dev.tribe29.com:30035 > /tmp/agentoutput
