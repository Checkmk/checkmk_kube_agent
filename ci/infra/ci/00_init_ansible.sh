echo "install ansible-plabook and ansible-galaxy:"
echo "pip install -U pip wheel"
echo "pip install -r ansible/requirements.txt"
cd ansible
ansible-galaxy install -r requirements.yml
