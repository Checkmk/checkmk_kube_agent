#!groovy

/// file: build-kube-agent.groovy

import java.text.SimpleDateFormat
import org.jenkinsci.plugins.pipeline.modeldefinition.Utils
import groovy.transform.Field


def run_in_ash(command, get_stdout=false) {
    return sh(script: "#!/bin/ash\n${command}", returnStdout: get_stdout);
}

def validate_parameters_and_branch(method, version, branch) {
    // This function validates the parameters in combination with the branch to be built from
    if (method == "rebuild_version" && version == "") error "You need to specify VERSION when rebuilding one!"
    if (method == "major") error "We currently only do major releases manually by creating a new branch!"
    if (branch == "main" && method != "daily") error "We currently only create daily builds from branch main!"
}

def determine_docker_tag(is_release_build, version) {
    if (is_release_build) {
        return version;
    }
    return "main_${(new SimpleDateFormat("yyyy.MM.dd")).format(new Date())}";
}

def main() {
    withEnv(["GIT_AUTHOR_NAME=Checkmk release system",
             "GIT_AUTHOR_EMAIL='feedback@check-mk.org'",
             "GIT_SSH_VARIANT=ssh",
             "GIT_COMMITTER_NAME=Checkmk release system",
             "GIT_COMMITTER_EMAIL=feedback@check-mk.org"]) {

        def kube_agent_github_repo = "tribe29/checkmk_kube_agent";
        def kube_agent_github_url = "https://github.com/${kube_agent_github_repo}";
        def github_pages_branch = "gh-pages";
        def ci_image_name = "checkmk-kube-agent-ci";

        def branch = scm.branches[0].name;
        def version = params.VERSION;
        def method = params.METHOD;
        def is_release_build = (method != "daily");
        def push_to_dockerhub = params.PUSH_TO_DOCKERHUB;
        
        print("VERSION:                 ${params.VERSION}");
        print("METHOD:                  ${params.METHOD}");
        print("PUSH_TO_DOCKERHUB:       ${params.PUSH_TO_DOCKERHUB}");
        print("branch:                  ${branch}");
        print("version:                 ${version}");
        print("method:                  ${method}");
        print("kube_agent_github_repo:  ${kube_agent_github_repo}");
        print("kube_agent_github_url:   ${kube_agent_github_url}");
        print("github_pages_branch:     ${github_pages_branch}");
        print("ci_image_name:           ${ci_image_name}");
        print("push_to_dockerhub:       ${push_to_dockerhub}");
        print("is_release_build:        ${is_release_build}");

        validate_parameters_and_branch(method, version, branch);

        def git_commit_id;
        // TODO: at least consolidate in this repo...
        def docker_group_id = sh(script: "getent group docker | cut -d: -f3", returnStdout: true);
        def helm_repo_index_file = "index.yaml";
        def STAGE_PUSH_IMAGES = 'Push Images';

        stage('Setup workspace and git clone') {
            sh("git clean -fd");
            sh("git remote add github git@github.com:${kube_agent_github_repo}.git || true");
        }

        stage('Build CI Image') {
            def x = docker.build(ci_image_name, "--network=host -f docker/ci/Dockerfile .");
            print("x: ${x}");
        }
        
        def ci_image = docker.image(ci_image_name);

        if (is_release_build) {
            stage('Calculate Version') {
                if (method != "rebuild_version") {
                    ci_image.inside("--entrypoint=") {
                        version = run_in_ash("METHOD=${method} make print-bumped-version", true).toString().trim();
                    }
                }
            }

            stage("Create or switch to tag") {
                withCredentials([sshUserPrivateKey(credentialsId: "release", keyFileVariable: 'keyfile')]) {
                    withEnv(["GIT_SSH_COMMAND=ssh -o \"StrictHostKeyChecking no\" -i ${keyfile} -l release"]) {
                        ci_image.inside("--entrypoint=") {
                            // FIXME run_in_ash("ci/jenkins/scripts/tagging.sh ${version} ${method} ${branch}")
                        }
                    }
                }
                git_commit_id = sh(script: "git rev-list -n 1 v${version}", returnStdout: true).toString().trim();
            }
            
            // The tag must exist on github in order to be able to use it to create a github release later
            // This can be deleted if the push to github can be triggered some other way (see CMK-9584)
            conditional_stage("Push to github", method != "rebuild_version") {
                withCredentials([sshUserPrivateKey(credentialsId: "ssh_private_key_lisa_github", keyFileVariable: 'keyfile')]) {
                    withEnv(["GIT_SSH_COMMAND=ssh -o \"StrictHostKeyChecking no\" -i ${keyfile}"]) {
                        ci_image.inside("--entrypoint=") {
                            // FIXME  run_in_ash("git push --tags github ${branch}")
                        }
                    }
                }
            }
        }

        stage("Build source and wheel package") {
            ci_image.inside("--entrypoint=") {
                run_in_ash("make dist");
            }
        }

        stage("Build Images") {
            def docker_image_tag = determine_docker_tag(is_release_build, version);
            ci_image.inside("-v /var/run/docker.sock:/var/run/docker.sock --group-add=${docker_group_id} --entrypoint=") {
                run_in_ash("make DOCKER_IMAGE_TAG=${docker_image_tag} release-image");
            }
            conditional_stage("Push Images", params.PUSH_TO_DOCKERHUB) {
                withCredentials([
                    usernamePassword(
                        credentialsId: '11fb3d5f-e44e-4f33-a651-274227cc48ab',
                        passwordVariable: 'DOCKER_PASSPHRASE',
                        usernameVariable: 'DOCKER_USERNAME')]) {
                    ci_image.inside("-v /var/run/docker.sock:/var/run/docker.sock --group-add=${docker_group_id} --entrypoint=") {
                        run_in_ash('echo \"${DOCKER_PASSPHRASE}\" | docker login -u ${DOCKER_USERNAME} --password-stdin');
                        // FIXME run_in_ash("make DOCKER_IMAGE_TAG=${docker_image_tag} push-images");
                    }
                }
            }
        }

        if (is_release_build) {
            withCredentials([
                usernamePassword(
                    credentialsId: "github-token-lisa",
                    passwordVariable: 'GH_TOKEN',
                    usernameVariable: "GH_USER")]) {
                conditional_stage("Delete github release", method == "rebuild_version") {
                    ci_image.inside("--entrypoint=") {
                        // FIXME run_in_ash("gh release delete --repo ${kube_agent_github_repo} -y v${version}")
                    }
                }
                stage("Create github release, upload helm chart artifact") {
                    ci_image.inside("--entrypoint=") {
                        // Note: see more details on the "gh" tool in the Dockerfile of the CI image.
                        // FIXME 
                        /*
                        run_in_ash("""
                            gh release create \
                                --repo=${kube_agent_github_repo} \
                                --target=${git_commit_id} \
                                --notes='' \
                                --title=v${version} \
                                v${version} \
                                dist-helm/checkmk-kube-agent-helm-${version}.tgz
                        """);
                        */
                    }
                }
            }
            conditional_stage("Update helm repo index", method != "rebuild_version") {
                sh("git checkout ${github_pages_branch}");
                withCredentials([sshUserPrivateKey(credentialsId: "release", keyFileVariable: 'keyfile')]) {
                    withEnv(["GIT_SSH_COMMAND=ssh -o \"StrictHostKeyChecking no\" -i ${keyfile} -l release"]) {
                        ci_image.inside("--entrypoint=") {
                            // FIXME 
                            /*
                            run_in_ash("""
                                scripts/update-helm-repo.sh \
                                --github-pages ${github_pages_branch} \
                                --helm-repo-index ${helm_repo_index_file} \
                                --url ${kube_agent_github_repo} \
                                --version ${version}""");
                            */
                        }
                    }
                }
                // This can be deleted if the push to github can be triggered some other way (see CMK-9584)
                withCredentials([sshUserPrivateKey(credentialsId: "ssh_private_key_lisa_github", keyFileVariable: 'keyfile')]) {
                    withEnv(["GIT_SSH_COMMAND=ssh -o \"StrictHostKeyChecking no\" -i ${keyfile}"]) {
                        ci_image.inside("--entrypoint=") {
                            run_in_ash("git checkout ${github_pages_branch}");
                            // FIXME run_in_ash("git push github ${github_pages_branch}");
                            sh("git checkout ${branch}");
                        }
                    }
                }
            }
        }
    }
}
return this;



