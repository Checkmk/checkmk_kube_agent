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

def NODE = "";

withFolderProperties {
    NODE = env.BUILD_NODE;
}

timeout(time: 12, unit: "HOURS") {
    node(NODE) {
        ansiColor("xterm") {
            main();
        }
    }
}

def main() {
    def snapshot_name = "hello_world";  // TODO: make this dynamic
    def nexus_url = DOCKER_REGISTRY_K8S; // DOCKER_REGISTRY_K8S is a global variable that magically appears
    def dry_run = DRY_RUN.toBoolean();

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

    stage("Cleanup checkout") {
        checkout(scm);
    }

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
    withEnv(["NEXUS_URL=${nexus_url}/v2"]) {
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
        withEnv([
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
                if (!dry_run) {
                    image.inside() {
                        sh("#!/bin/ash\n${command}");
                    }
                }
        }
    }
}
