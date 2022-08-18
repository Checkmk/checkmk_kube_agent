properties([
    buildDiscarder(logRotator(
        artifactDaysToKeepStr: "",
        artifactNumToKeepStr: "",
        daysToKeepStr: "7",
        numToKeepStr: "200")),
    parameters([
        choice(choices: ['containerd', 'docker'], name: 'CONTAINER_RUNTIME',
                description: '<b>Choose the container runtime that will be installed.</b>'),
        choice(choices: ['1.21', '1.22', '1.23'], name: 'KUBERNETES_VERSION',
                description: '<b>Choose the Kubernetes version that will be installed.</b>'),
        string(name: 'PM_NODE', defaultValue: '', description: 'Proxmox node' ),
        string(name: 'PM_DOMAIN', defaultValue: '', description: 'Proxmox domain' ),
        string(name: 'PM_SEARCHDOMAIN', defaultValue: '', description: 'Proxmox searchdomain' ),
        string(name: 'PM_HOST', defaultValue: '', description: 'Proxmox host address' ),
    ])
])

def NODE = "";

withFolderProperties {
    NODE = env.BUILD_NODE;
}

timeout(time: 12, unit: "HOURS") {
    node(NODE) {
        ansiColor("xterm") {
            do_it();
        }
    }
}


def do_it() {
    def ANSIBLE_DIR = "ci/integration/ansible";
    def ANSIBLE_HOSTS_FILE = "${ANSIBLE_DIR}/inventory/hosts.ini";
    def ANSIBLE_PLAYBOOKS_DIR = "${ANSIBLE_DIR}/playbooks";
    def CADVISOR_IMAGE_NAME = "cadvisor-integration";
    def COLLECTOR_IMAGE_NAME = "kubernetes-collector-integration";
    def DOCKER_GROUP_ID = sh(script: "getent group docker | cut -d: -f3", returnStdout: true);
    def DOCKER_IMAGE_TAG = env.GIT_COMMIT;
    def DOCKERHUB_PUBLISHER = DOCKER_REGISTRY_K8S.replace("https://", "");  // DOCKER_REGISTRY_K8S is a global variable that magically appears
    def IMAGE;
    def KUBERNETES_VERSION_STR = KUBERNETES_VERSION.replace(".", "");
    def PM_URL = "https://${PM_HOST}:8006";
    def RUN_HOSTS = "k8s_${KUBERNETES_VERSION_STR}_${CONTAINER_RUNTIME}";
    def RELEASER_IMAGE;
    def SNAPSHOT_NAME = "hello_world";

    stage("check out") {
        println("hello")
        checkout(scm);
        // delete any untracked files, such as kube config from any previous integration runs
        sh("git clean -fd");
    }
    stage("build CI image") {
        RELEASER_IMAGE = docker.build("checkmk-kube-agent-ci", "--network=host -f docker/ci/Dockerfile .");
        IMAGE = docker.build("checkmk-kube-agent-integration", "--network=host --target=integration-tester -f docker/ci/Dockerfile .");
    }
    stage("build release image") {
        RELEASER_IMAGE.inside("-v /var/run/docker.sock:/var/run/docker.sock --group-add=${DOCKER_GROUP_ID}") {
            ash("make DOCKERHUB_PUBLISHER=${DOCKERHUB_PUBLISHER} COLLECTOR_IMAGE_NAME=${COLLECTOR_IMAGE_NAME} CADVISOR_IMAGE_NAME=${CADVISOR_IMAGE_NAME} DOCKER_IMAGE_TAG=${DOCKER_IMAGE_TAG} release-image");
        }
    }
    stage("push image to Nexus") {
        docker.withRegistry(DOCKER_REGISTRY_K8S, "nexus") {
            RELEASER_IMAGE.inside("-v /var/run/docker.sock:/var/run/docker.sock --group-add=${DOCKER_GROUP_ID}") {
                ash("docker push ${DOCKERHUB_PUBLISHER}/${COLLECTOR_IMAGE_NAME}:${DOCKER_IMAGE_TAG}");
                ash("docker push ${DOCKERHUB_PUBLISHER}/${CADVISOR_IMAGE_NAME}:${DOCKER_IMAGE_TAG}");
            }
        }
    }
    stage("roll VMs back to snapshot") {
        withCredentials([usernamePassword(credentialsId: "kube_at_proxmox", passwordVariable: "PM_PASS", usernameVariable: "PM_USER")]) {
            withEnv(["PM_NODE=${PM_NODE}", "PM_HOST=${PM_HOST}", "PM_URL=${PM_URL}"]) {
                IMAGE.inside() {
                    ash("ansible-playbook --inventory ${ANSIBLE_HOSTS_FILE} ${ANSIBLE_PLAYBOOKS_DIR}/snapshot.yml --extra-vars 'run_hosts=${RUN_HOSTS} snap_state=rollback snap_name=${SNAPSHOT_NAME}'");
                }
            }
        }
    }
    stage("start VMs") {
        withCredentials([usernamePassword(credentialsId: "kube_at_proxmox", passwordVariable: "PM_PASS", usernameVariable: "PM_USER"), sshUserPrivateKey(credentialsId: "ssh_kube_ansible", keyFileVariable: "ANSIBLE_SSH_PRIVATE_KEY_FILE", usernameVariable: "ANSIBLE_SSH_REMOTE_USER")]) {
            withEnv(["PM_NODE=${PM_NODE}", "PM_HOST=${PM_HOST}", "PM_URL=${PM_URL}"]) {
                IMAGE.inside() {
                    ash("ansible-playbook --inventory ${ANSIBLE_HOSTS_FILE} ${ANSIBLE_PLAYBOOKS_DIR}/manage.yml --extra-vars 'run_hosts=${RUN_HOSTS} target_state=started'");
                }
            }
        }
    }
    IMAGE.inside() {
        stage("download kube config file") {
            withCredentials([sshUserPrivateKey(credentialsId: "ssh_kube_ansible", keyFileVariable: "ANSIBLE_SSH_PRIVATE_KEY_FILE", usernameVariable: "ANSIBLE_SSH_REMOTE_USER")]) {
                ash("ansible-playbook --inventory ${ANSIBLE_HOSTS_FILE} ${ANSIBLE_PLAYBOOKS_DIR}/auth.yml --extra-vars 'run_hosts=${RUN_HOSTS}'");
            }
        }
        stage("verify kube config") {
            ash("ls /home/jenkins/.kube");
            ash("kubectl get nodes");
        }
        // integration tests go here
    }
    stage("roll VMs back to snapshot") {
        withCredentials([usernamePassword(credentialsId: "kube_at_proxmox", passwordVariable: "PM_PASS", usernameVariable: "PM_USER")]) {
            withEnv(["PM_NODE=${PM_NODE}", "PM_HOST=${PM_HOST}", "PM_URL=${PM_URL}"]) {
                IMAGE.inside() {
                    ash("ansible-playbook --inventory ${ANSIBLE_HOSTS_FILE} ${ANSIBLE_PLAYBOOKS_DIR}/snapshot.yml --extra-vars 'run_hosts=${RUN_HOSTS} snap_state=rollback snap_name=${SNAPSHOT_NAME}'");
                }
            }
        }
    }
}

def ash(command) {
    sh("#!/bin/ash\n${command}");
}
