#!groovy

/// file: provision.groovy

def main() {
    def kubernetes_string = params.KUBERNETES_VERSION.replace(".", "");
    def snapshot_name = "${params.CONTAINER_RUNTIME}_${kubernetes_string}";
    def nexus_url = "${DOCKER_REGISTRY_K8S}/v2"; // DOCKER_REGISTRY_K8S is a global variable that magically appears
    def dry_run = params.DRY_RUN.toBoolean();

    print(
        """
        |===== CONFIGURATION ===============================
        |KUBERNETES_VERSION:    |${params.KUBERNETES_VERSION}│
        |CONTAINER_RUNTIME:     |${params.CONTAINER_RUNTIME}│
        |PROXMOX_NODE:          |${env.PROXMOX_NODE}│
        |PROXMOX_DOMAIN:        |${env.PROXMOX_DOMAIN}│
        |DRY_RUN:               |${dry_run}│
        |NEXUS_URL:             |${nexus_url}│
        |SNAPSHOT_NAME:         |${snapshot_name}│
        |===================================================
        """.stripMargin());

    def image = { name ->
        stage("Build CI image") {
            return docker.build(name, "--network=host --target=integration-tester -f docker/ci/Dockerfile .");
        }
    }("checkmk-kube-agent-integration");

    stage("Destroy VMs") {
        run_ansible(image, dry_run, "destroy");
    }
    stage("Deploy VMs") {
        run_ansible(image, dry_run, "deploy");
    }
    stage("Start VMs") {
        run_ansible(image, dry_run, "manage", "target_state=started");
    }
    stage("Provision container runtime/kubernetes cluster") {
        run_ansible(image, dry_run, "provision");
    }

    withEnv(["NEXUS_URL=${nexus_url}"]) {
        withCredentials([
            usernamePassword(
                credentialsId: "k8s-read-only-nexus-docker",
                passwordVariable: "NEXUS_PASSWORD",
                usernameVariable: "NEXUS_USER")]) {
            stage("Provide credentials & ServiceAccount for Kubernetes") {
                run_ansible(image, dry_run, "post");
            }
        }
    }

    stage("Stop VMs") {
        run_ansible(image, dry_run, "manage", "target_state=stopped");
    }
    stage("Create snapshot") {
        run_ansible(image, dry_run, "snapshot", "snap_state=present snap_name=${snapshot_name}");
    }
}

def run_ansible(image, dry_run, operation, extra_vars="") {
    def ansible_dir = "ci/integration/ansible";
    def ansible_hosts_file = "${ansible_dir}/inventory/hosts.ini";
    def ansible_playbooks_dir = "${ansible_dir}/playbooks";
    def kubernetes_version_str = params.KUBERNETES_VERSION.replace(".", "");
    def pm_url = "https://${env.PROXMOX_HOST}:8006";
    def run_hosts = "k8s_${kubernetes_version_str}_${params.CONTAINER_RUNTIME}";
    def command = """
        ansible-playbook \
            --inventory ${ansible_hosts_file} ${ansible_playbooks_dir}/${operation}.yml \
            --extra-vars 'run_hosts=${run_hosts} ${extra_vars}'
    """;

    withCredentials([
        sshUserPrivateKey(
            credentialsId: "ssh_kube_ansible",
            keyFileVariable: "ANSIBLE_SSH_PRIVATE_KEY_FILE",
            usernameVariable: "ANSIBLE_SSH_REMOTE_USER"),
        usernamePassword(
            credentialsId: "kube_at_proxmox",
            passwordVariable: "PM_PASS",
            usernameVariable: "PM_USER")]) {
        withEnv([   // FIXME: use proxmox_env
            "PM_NODE=${env.PROXMOX_NODE}",
            "PM_HOST=${env.PROXMOX_HOST}",
            "PM_URL=${pm_url}"]) {
                print("""
                    Running ${operation}
                    Using credentials: ssh_kube_ansible, kube_at_proxmox
                    Using environment variables: \
                        PM_NODE=${env.PROXMOX_NODE}, \
                        PM_HOST=${env.PROXMOX_HOST_HOST}, \
                        PM_URL=${pm_url}, \
                        PM_SEARCHDOMAIN=${env.PROXMOX_SEARCHDOMAIN}
                    ${command}
                """);
                image.inside() {
                   ash("#!/bin/ash\n${command}", dry_run);
                }
        }
    }
}

// FIXME: extract function along with duplicate from integration-testing.groovy to job-entry.groovy
def ash(command, dry_run) {
    if (!dry_run) {
        sh("#!/bin/ash\n${command}");
    } else {
        print(command);
    }
}

return this;
