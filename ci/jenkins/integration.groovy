properties([
    buildDiscarder(logRotator(
        artifactDaysToKeepStr: "",
        artifactNumToKeepStr: "",
        daysToKeepStr: "7",
        numToKeepStr: "200")),
])

def NODE = "";

withFolderProperties {
    NODE = env.BUILD_NODE;
}

timeout(time: 12, unit: "HOURS") {
    node(NODE) {
        do_it();
    }
}


def do_it() {
    def ANSIBLE_DIR = "ci/infra/ansible";
    def IMAGE;
    stage("check out") {
        checkout(scm);
    }
    stage("build CI image") {
        IMAGE = docker.build("checkmk-kube-agent-ci", "--network=host -f docker/ci/Dockerfile .");
    }
    stage("initialise terraform") {
        run_terraform(IMAGE, "init -input=false");
    }
    stage("destroy") {
        run_terraform(IMAGE, "destroy -auto-approve");
    }
    stage("create terraform plan") {
        run_terraform(IMAGE, "plan -out plan");
    }
    stage("apply terraform plan") {
        run_terraform(IMAGE, "apply -auto-approve plan");
    }
    stage("run ansible playbook") {
        run_ansible(IMAGE, "ansible-playbook --ssh-extra-args '-o StrictHostKeyChecking=no' -u test -i ${ANSIBLE_DIR}/inventory/hosts ${ANSIBLE_DIR}/playbooks/provision.yml --extra-vars 'kubernetes_version=1.23 container_runtime=containerd checkmk_kube_agent_path=${WORKSPACE}' --tags 'common,containerd'");
    }
    //stage("run ansible playbook") {
    //    withCredentials([sshUserPrivateKey(credentialsId: "ssh_kube_ansible", keyFileVariable: "ANSIBLE_SSH_PRIVATE_KEY_FILE")]) {
    //        IMAGE.inside() {
    //            sh("#!/bin/ash\nansible-playbook --key-file ${ANSIBLE_SSH_PRIVATE_KEY_FILE} --ssh-extra-args '-o StrictHostKeyChecking=no' -u test -i ${ANSIBLE_DIR}/inventory/hosts ${ANSIBLE_DIR}/playbooks/provision.yml --extra-vars 'kubernetes_version=1.23 container_runtime=containerd checkmk_kube_agent_path=${WORKSPACE}' --tags 'common,containerd'");
    //        }
    //    }
    //}
    stage("destroy") {
        run_terraform(IMAGE, "destroy -auto-approve");
    }
}

def run_terraform(image, cmd) {
    def TERRAFORM_DIR = "ci/infra/terraform";
    withCredentials([usernamePassword(credentialsId: "ssh_kube_terraform", passwordVariable: "PM_PASS", usernameVariable: "PM_USER")]) {
        image.inside() {
            sh("#!/bin/ash\nterraform -chdir=${TERRAFORM_DIR} ${cmd}");
        }
    }
}

def run_ansible(image, cmd) {
    withCredentials([sshUserPrivateKey(credentialsId: "ssh_kube_ansible", keyFileVariable: "ANSIBLE_SSH_PRIVATE_KEY_FILE")]) {
        image.inside() {
            sh("#!/bin/ash\n${cmd}");
        }
    }
}
