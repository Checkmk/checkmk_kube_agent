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
        booleanParam(name: 'DRY_RUN', defaultValue: false, description: 'Set to true if you want to print the actions to stdout, rather than execute them (e.g. for debugging).'),
    ])
])

DRY_RUN = DRY_RUN.toBoolean();
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
    def IMAGE;
    def SNAPSHOT_NAME = "hello_world";
    def NEXUS_URL = DOCKER_REGISTRY_K8S; // DOCKER_REGISTRY_K8S is a global variable that magically appears

    stage("check out") {
        checkout(scm);
        println "Provisioning Kubernetes v${KUBERNETES_VERSION} running with ${CONTAINER_RUNTIME} to node ${env.PROXMOX_NODE}.${env.PROXMOX_DOMAIN}";
        println "Dry run: ${DRY_RUN}";
    }
    stage("build CI image") {
        IMAGE = docker.build("checkmk-kube-agent-integration", "--network=host --target=integration-tester -f docker/ci/Dockerfile .");
    }
    stage("destroy VMs") {
        run_ansible(IMAGE, "destroy");
    }
    stage("deploy VMs") {
        run_ansible(IMAGE, "deploy");
    }
    stage("start VMs") {
        run_ansible(IMAGE, "manage", "target_state=started");
    }
    stage("provision container runtime/kubernetes cluster") {
        run_ansible(IMAGE, "provision");
    }
    withEnv(["NEXUS_URL=${NEXUS_URL}/v2"]) {
        withCredentials([usernamePassword(credentialsId: "k8s-read-only-nexus-docker", passwordVariable: "NEXUS_PASSWORD", usernameVariable: "NEXUS_USER")]) {
            stage("provide private registry credentials") {
                run_ansible(IMAGE, "post");
            }
        }
    }
    stage("stop VMs") {
        run_ansible(IMAGE, "manage", "target_state=stopped");
    }
    stage("create snapshot") {
        run_ansible(IMAGE, "snapshot", "snap_state=present snap_name=${SNAPSHOT_NAME}");
    }
}

def run_ansible(image, operation, extra_vars="") {
    def ANSIBLE_DIR = "ci/integration/ansible";
    def ANSIBLE_HOSTS_FILE = "${ANSIBLE_DIR}/inventory/hosts.ini";
    def ANSIBLE_PLAYBOOKS_DIR = "${ANSIBLE_DIR}/playbooks";
    def KUBERNETES_VERSION_STR = KUBERNETES_VERSION.replace(".", "");
    def PM_URL = "https://${env.PROXMOX_HOST}:8006";
    def RUN_HOSTS = "k8s_${KUBERNETES_VERSION_STR}_${CONTAINER_RUNTIME}";
    def COMMAND = "ansible-playbook --inventory ${ANSIBLE_HOSTS_FILE} ${ANSIBLE_PLAYBOOKS_DIR}/${operation}.yml --extra-vars 'run_hosts=${RUN_HOSTS} ${extra_vars}'";

    withCredentials([sshUserPrivateKey(credentialsId: "ssh_kube_ansible", keyFileVariable: "ANSIBLE_SSH_PRIVATE_KEY_FILE", usernameVariable: "ANSIBLE_SSH_REMOTE_USER"),
                     usernamePassword(credentialsId: "kube_at_proxmox", passwordVariable: "PM_PASS", usernameVariable: "PM_USER")]) {
        withEnv(["PM_NODE=${env.PROXMOX_NODE}", "PM_HOST=${env.PROXMOX_HOST}", "PM_URL=${PM_URL}"]) {
            println "Running ${operation}"
            println "Using credentials: ssh_kube_ansible, kube_at_proxmox";
            println "Using environment variables: PM_NODE=${env.PROXMOX_NODE}, PM_HOST=${env.PROXMOX_HOST_HOST}, PM_URL=${PM_URL}, PM_SEARCHDOMAIN=${env.PROXMOX_SEARCHDOMAIN}";
            println COMMAND;
            if (!DRY_RUN) {
                image.inside() {
                    sh("#!/bin/ash\n${COMMAND}");
                }
            }
        }
    }
}
