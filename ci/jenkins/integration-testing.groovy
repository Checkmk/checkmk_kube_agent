#!groovy

/// file: integration-testing.groovy

def main() {
    def dockerhub_publisher = DOCKER_REGISTRY_K8S.replace("https://", "");  // DOCKER_REGISTRY_K8S is a global variable that magically appears
    // TODO: should use commit hash as image tag instead of build id (not unique)
    def docker_image_tag = env.BUILD_ID;
    def cadvisor_image_name = "cadvisor-integration";
    def collector_image_name = "kubernetes-collector-integration";
    def kubernetes_string = params.KUBERNETES_VERSION.replace(".", "");
    def snapshot_name = "${params.CONTAINER_RUNTIME}_${kubernetes_string}";

    print(
        """
        |===== CONFIGURATION ===============================
        |KUBERNETES_VERSION:    |${params.KUBERNETES_VERSION}│
        |CONTAINER_RUNTIME:     |${params.CONTAINER_RUNTIME}│
        |PROXMOX_NODE:          |${env.PROXMOX_NODE}│
        |PROXMOX_HOST:          |${env.PROXMOX_HOST}│
        |dockerhub_publisher:   |${dockerhub_publisher}│
        |docker_image_tag:      |${docker_image_tag}│
        |snapshot_name:         |${snapshot_name}|
        |===================================================
        """.stripMargin());

    def mount_docker_sock = "-v /var/run/docker.sock:/var/run/docker.sock";
    def add_docker_group_id = "--group-add=${sh_output('getent group docker | cut -d: -f3')}";

    stage("Cleanup checkout") {
        // delete any untracked files, such as kube config from any previous integration runs
        sh("git clean -fd");
    }

    def releaser_image = { name ->
        stage("Build CI Releaser image") {
            return docker.build(name, "--network=host -f docker/ci/Dockerfile .");
        }
    }("checkmk-kube-agent-ci");

    stage("Build release image") {
        releaser_image.inside("${mount_docker_sock} ${add_docker_group_id}") {
            ash("""
                make \
                    DOCKERHUB_PUBLISHER=${dockerhub_publisher} \
                    COLLECTOR_IMAGE_NAME=${collector_image_name} \
                    CADVISOR_IMAGE_NAME=${cadvisor_image_name} \
                    DOCKER_IMAGE_TAG=${docker_image_tag} \
                    release-image
            """);
        }
    }

    stage("Push image to Nexus") {
        docker.withRegistry(DOCKER_REGISTRY_K8S, "nexus") {
            releaser_image.inside("${mount_docker_sock} ${add_docker_group_id}") {
                ash("docker push ${dockerhub_publisher}/${collector_image_name}:${docker_image_tag}");
                ash("docker push ${dockerhub_publisher}/${cadvisor_image_name}:${docker_image_tag}");
            }
        }
    }

    def tester_image = { name ->
        stage("Build Tester image") {
            return docker.build(name, "--network=host --target=integration-tester -f docker/ci/Dockerfile .");
        }
    }("checkmk-kube-agent-integration");

    tester_image.inside() {
        def ansible_dir = "ci/integration/ansible";
        def ansible_hosts_file = "${ansible_dir}/inventory/hosts.ini";
        def ansible_playbooks_dir = "${ansible_dir}/playbooks";
        def pm_url = "https://${env.PROXMOX_HOST}:8006";
        def run_hosts = "k8s_${KUBERNETES_VERSION.replace('.', '')}_${CONTAINER_RUNTIME}";
        def proxmox_env = ["PM_NODE=${env.PROXMOX_NODE}", "PM_HOST=${env.PROXMOX_HOST}", "PM_URL=${pm_url}"];

        stage("Roll VMs back to snapshot"){
            withCredentials([
                usernamePassword(
                    credentialsId: "kube_at_proxmox",
                    passwordVariable: "PM_PASS",
                    usernameVariable: "PM_USER")]) {
                withEnv(proxmox_env) {
                    ash("""
                        ansible-playbook \
                            --inventory ${ansible_hosts_file} \
                            ${ansible_playbooks_dir}/snapshot.yml \
                            --extra-vars 'run_hosts=${run_hosts} snap_state=rollback snap_name=${snapshot_name}'
                    """);
                }
            }
        }

        stage("Start VMs") {
            withCredentials([
                usernamePassword(
                    credentialsId: "kube_at_proxmox",
                    passwordVariable: "PM_PASS",
                    usernameVariable: "PM_USER"),
                sshUserPrivateKey(
                    credentialsId: "ssh_kube_ansible",
                    keyFileVariable: "ANSIBLE_SSH_PRIVATE_KEY_FILE",
                    usernameVariable: "ANSIBLE_SSH_REMOTE_USER")]) {
                withEnv(proxmox_env) {
                    ash("""
                        ansible-playbook \
                            --inventory ${ansible_hosts_file} \
                            ${ansible_playbooks_dir}/manage.yml \
                            --extra-vars 'run_hosts=${run_hosts} target_state=started'
                    """);
                }
            }
        }

        stage("Download kube config file") {
            withCredentials([
                sshUserPrivateKey(
                    credentialsId: "ssh_kube_ansible",
                    keyFileVariable: "ANSIBLE_SSH_PRIVATE_KEY_FILE",
                    usernameVariable: "ANSIBLE_SSH_REMOTE_USER")]) {
                ash("""
                    ansible-playbook \
                        --inventory ${ansible_hosts_file} \
                        ${ansible_playbooks_dir}/auth.yml \
                        --extra-vars 'run_hosts=${run_hosts}'
                """);
            }
        }

        stage("Verify kube config") {
            ash("ls /home/jenkins/.kube");
            ash("kubectl get nodes");
        }

        def kubernetes_endpoint = {
            stage("Get Kubernetes cluster endpoint") {
                return ash_output("""
                    kubectl config view --minify \
                    | grep server \
                    | cut -f 2- -d ':' \
                    | tr -d ' '
                """);
            }
        }();
        println(kubernetes_endpoint);

        def api_token = {
            stage("Get token from deployed serviceaccount") {
                ash("kubectl get serviceaccounts -A");
                return ash_output("""
                    kubectl get secret \$(\
                            kubectl get serviceaccount supervisor \
                            -o=jsonpath='{.secrets[*].name}' \
                            -n checkmk-integration) \
                        -n checkmk-integration \
                        -o=jsonpath='{.data.token}' \
                    | base64 -d
                """);
            }
        }();
        println(api_token);

        stage("Execute integration tests") {
            ash("ls");
            ash("""
                pytest tests/integration \
                    --cluster-endpoint=${kubernetes_endpoint} \
                    --cluster-token=${api_token} \
                    --cluster-workers=2 \
                    --image-registry=${dockerhub_publisher} \
                    --image-pull-secret-name=registry-auth \
                    --collector-image-name=${collector_image_name} \
                    --cadvisor-image-name=${cadvisor_image_name} \
                    --image-tag=${docker_image_tag}
            """);
        }

        stage("Roll VMs back to snapshot") {
            withCredentials([
                usernamePassword(
                    credentialsId: "kube_at_proxmox",
                    passwordVariable: "PM_PASS",
                    usernameVariable: "PM_USER")]) {
                withEnv(proxmox_env) {
                    ash("""
                        ansible-playbook \
                            --inventory ${ansible_hosts_file} \
                            ${ansible_playbooks_dir}/snapshot.yml \
                            --extra-vars 'run_hosts=${run_hosts} snap_state=rollback snap_name=${snapshot_name}'
                    """);
                }
            }
        }
    }
}

return this;
