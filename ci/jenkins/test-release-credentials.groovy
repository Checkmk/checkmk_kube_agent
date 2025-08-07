#!groovy

/// file: test-release-credentials.groovy

def run_in_ash(command, get_stdout=false) {
    ash_command = "#!/bin/ash\n" + command;
    return sh(script: "${ash_command}", returnStdout: get_stdout);
}

def main() {
        currentBuild.description = '\nTest credentials required by the release job\n';
        def KUBE_AGENT_GITHUB_REPO = "checkmk/checkmk_kube_agent";
        def CI_IMAGE = "checkmk-kube-agent-ci";
        def GITHUB_SSH_CREDENTIAL_ID = "ssh_private_key_github_kubernetes";
        def GITHUB_TOKEN_CREDENTIAL_ID = "github-token-CheckmkCI-kubernetes";

        stage('Checkout Sources') {
            checkout(scm);
            sh("git clean -fd");
        }

        docker.build(CI_IMAGE, "--network=host -f docker/ci/Dockerfile .");

        stage("Test ${GITHUB_SSH_CREDENTIAL_ID}") {
            withCredentials([file(credentialsId: GITHUB_SSH_CREDENTIAL_ID, variable: "keyfile")]) {
                docker.image(CI_IMAGE).inside("--entrypoint=") {
                    // The exit code of the below command is 1 even though the
                    // authentication has been successful. This is because Github does not provide
                    // shell access, and returns an error code as per 'ssh' spec. The error codes are:
                    // 1: authentication is successful
                    // 255: authentication is not successful
                    run_in_ash("ssh -o StrictHostKeyChecking=no -i ${keyfile} -T git@github.com; [[ \$? == 1 ]]");
                }
            }
        }

        stage("Test ${GITHUB_TOKEN_CREDENTIAL_ID}") {
            withCredentials([usernamePassword(credentialsId: GITHUB_TOKEN_CREDENTIAL_ID, passwordVariable: 'GH_TOKEN', usernameVariable: "GH_USER")]) {
               docker.image(CI_IMAGE).inside("--entrypoint=") {
                   run_in_ash("gh release list --repo ${KUBE_AGENT_GITHUB_REPO}");
               }
            }
        }
}

return this;
