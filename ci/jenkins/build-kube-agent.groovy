#!groovy

/// file: build-kube-agent.groovy

import java.text.SimpleDateFormat
import org.jenkinsci.plugins.pipeline.modeldefinition.Utils

def main() {
    currentBuild.description = '\nBuilding the Kubernetes Agent\n';

    def is_release_build = false;
    switch (params.METHOD) {
        case "daily":
            is_release_build = false;
            break;
        default:
            is_release_build = true;
            break;
    }

    def this_branch = safe_branch_name();

    validate_parameters_and_branch(params.METHOD, params.VERSION, this_branch);

    withEnv([
        "GIT_AUTHOR_NAME=Checkmk release system",
        "GIT_AUTHOR_EMAIL='feedback@check-mk.org'",
        "GIT_SSH_VARIANT=ssh",
        "GIT_COMMITTER_NAME=Checkmk release system",
        "GIT_COMMITTER_EMAIL=feedback@check-mk.org",
    ]) {
        main_for_real(this_branch, params.METHOD, params.VERSION, is_release_build);
    }
}

def branch_name() {
    if (params.CUSTOM_GIT_REF) {
        if (branch_name_is_branch_version("${checkout_dir}")) {
            // this is only required as "master" is called "stable branch + 0.1.0"
            // e.g. 2.3.0 (stable) + 0.1.0 = 2.4.0
            return env.GERRIT_BRANCH ?: get_branch_version("${checkout_dir}");
        } else {
            return env.GERRIT_BRANCH ?: "main";
        }
    } else {
        // defined in global-defaults.yml
        return env.GERRIT_BRANCH ?: branches_str;
    }
}

def safe_branch_name() {
    return branch_name().replaceAll("/", "-");
}

def run_in_ash(command, get_stdout=false) {
    ash_command = "#!/bin/ash\n" + command;
    return sh(script: "${ash_command}", returnStdout: get_stdout);
}

def validate_parameters_and_branch(method, version, branch) {
    // This function validates the parameters in combination with the branch to be built from
    if (method == "rebuild_version" && version == "") error "You need to specify VERSION when rebuilding one!"
    if (method == "major") error "We currently only do major releases manually by creating a new branch!"
    if (branch == "main" && method != "daily") error "We currently only create daily builds from branch main!"
}

def determine_docker_tag(is_release_build) {
    def docker_tag = "";

    if (is_release_build) {
        docker_tag = params.VERSION;
    }
    else {
        def date_now = new Date();
        def date_format = new SimpleDateFormat("yyyy.MM.dd");
        def date_str = date_format.format(date_now);
        docker_tag = "main_${date_str}";
    }

    return docker_tag;
}

def main_for_real(this_branch, method, version, is_release_build) {
    /* Problem guide

    All release stages (not built) are independent from each other.
    Some components may be referenced by other components, but their individual release process
    does not block another

    The determined version number is used in almost all stages and can, therefore, be considered as main linking
    reference

    ## General Troubleshoot
    * Important: should never push commits directly to github from local branch (always through Gerrit)
        Github is like a mirror to the Gerrit repo
    ** encountered error case (for github pages branch): pushed commit locally which resulted in different
    git hashes between Gerrit & Github and therefore blocked the release during the subsequent run.
    ** example was https://github.com/checkmk/checkmk_kube_agent/commits/gh-pages (add helm chart version 1.1.0)
        different commit hashes between Gerrit gh-pages & github gh-pages
    ** resolving the error case: must hard reset & force push to Github branch
        Gerrit commits always represent the truth (not Github)


    ## Troubleshoot git tags
    * the version number is also used as git tag which is pushed to our internal branch
    * the tag is also pushed to Github

    # TODO: this approach is not suggested, so an alternative approach should be drafted
    * troubleshoot when only this stage succeeds: ->
        * the tag should be removed for both using git tag -d <tag_name>
        * depending on which stage fails, two branches must also be cleaned up:
            * the release branch (e.g. 1.0.0)
            * the github branch
        * do not forget to sanitize your local tags


    ## Troubleshoot container images
    * tag is also used for container images of the Cluster & Node Collector which are built and then docker pushed
    * in case there is stage failure after images were pushed: you can just leave the two images as they are since
    they will get overwritten with the next trigger
    * in case team decides to revert/cancel a release: the pushed images should be deleted

    ## Troubleshoot Github Release
    * a Github token is used to execute this stage;
        * troubleshoot: should almost never happen but you can verify if the token hasn't expired using `gh api`
    * github release must be deleted manually before another release with the same version name can be created
    * the releases can be verified here https://github.com/checkmk/checkmk_kube_agent/releases

    ## Troubleshoot Github Pages
    * KNOWN PROBLEM: the gh command line tool does not recognize files which are located in the /tmp (potentially
    also others) directory
    * see General Troubleshoot (above) if github push attempt fails

    */
    def commit_sha;
    // TODO: at least consolidate in this repo...
    def docker_group_id = sh(script: "getent group docker | cut -d: -f3", returnStdout: true);
    def github_pages_branch = "gh-pages";
    def kube_agent_github_repo = "checkmk/checkmk_kube_agent";
    def kube_agent_github_url = "https://github.com/${kube_agent_github_repo}";
    def ci_image = "checkmk-kube-agent-ci";
    def helm_repo_index_file="index.yaml";
    def stage_push_images = 'Push Images';
    def github_ssh_credential_id = "ssh_private_key_github_kubernetes";
    def github_token_credential_id = "github-token-CheckmkCI-kubernetes";
    def this_version = version;
    def make_parameters = "";
    def workspace_dir = sh(script: 'git rev-parse --show-toplevel', returnStdout: true).trim();

    stage('Checkout Sources') {
        sh("git remote add github git@github.com:${kube_agent_github_repo}.git || true");
    }
    docker.build(ci_image, "--network=host -f docker/ci/Dockerfile .");

    stage('Validate Github credentials') {
        build(
            job: "./validate-release-credentials",
        )
    }

    if (is_release_build) {
        stage('Calculate Version') {
            if (method != "rebuild_version") {
                docker.image(ci_image).inside("--entrypoint=") {
                    this_version = run_in_ash("METHOD=${method} make print-bumped-version", true).toString().trim();
                }
            }
        }

        stage("Create or switch to tag") {
            withCredentials([sshUserPrivateKey(credentialsId: "release", keyFileVariable: 'keyfile')]) {
                withEnv(["GIT_SSH_COMMAND=ssh -o \"StrictHostKeyChecking no\" -i ${keyfile} -l release"]) {
                    docker.image(ci_image).inside("--entrypoint=") {
                        run_in_ash("./ci/jenkins/scripts/tagging.sh ${this_version} ${method} ${this_branch}");
                    }
                }
            }
            commit_sha = sh(script: "git rev-list -n 1 v${this_version}", returnStdout: true).toString().trim();
        }
        // The tag must exist on github in order to be able to use it to create a github release later
        // This can be deleted if the push to github can be triggered some other way (see CMK-9584)
        if (method != "rebuild_version") {
            stage("Push to github") {
                withCredentials([file(credentialsId: "ssh_private_key_github_kubernetes", variable: 'keyfile')]) {
                    withEnv(["GIT_SSH_COMMAND=ssh -o \"StrictHostKeyChecking no\" -i ${keyfile}"]) {
                        docker.image(ci_image).inside("--entrypoint=") {
                            run_in_ash("git push --tags github ${this_branch}");
                        }
                    }
                }
            }
        }
        else {
            Utils.markStageSkippedForConditional("rebuild_version");
        }
    }

    stage("Build source and wheel package") {
        docker.image(ci_image).inside("--entrypoint=") {
            run_in_ash("make dist");
        }
    }

    stage("Build Images") {
        def docker_image_tag = determine_docker_tag(is_release_build);

        if (docker_image_tag != "") {
            // We only want to set a specific image tag if this has been set
            // to a non-empty value. If this is empty we let the logic in
            // the Makefile take over reading the version.
            make_parameters = "DOCKER_IMAGE_TAG=${docker_image_tag}";
        }

        docker.withRegistry(DOCKER_REGISTRY, 'nexus') {
            docker.image(ci_image).inside("-v /var/run/docker.sock:/var/run/docker.sock --group-add=${docker_group_id} --entrypoint=") {
                run_in_ash("make ${make_parameters} release-image");
            }
        }

    }

    stage(stage_push_images) {
        if (params.PUSH_TO_DOCKERHUB) {
            withCredentials([
                    usernamePassword(credentialsId: '11fb3d5f-e44e-4f33-a651-274227cc48ab', passwordVariable: 'DOCKER_PASSPHRASE', usernameVariable: 'DOCKER_USERNAME')]) {
                docker.image(ci_image).inside("-v /var/run/docker.sock:/var/run/docker.sock --group-add=${docker_group_id} --entrypoint=") {
                    run_in_ash('echo \"${DOCKER_PASSPHRASE}\" | docker login -u ${DOCKER_USERNAME} --password-stdin');
                    run_in_ash("make ${make_parameters} push-images");
                }
            }
        }
        else {
            Utils.markStageSkippedForConditional(stage_push_images);
        }
    }

    if (is_release_build) {
        withCredentials([usernamePassword(credentialsId: github_token_credential_id, passwordVariable: 'GH_TOKEN', usernameVariable: "GH_USER")]) {
            if (method == "rebuild_version") {
                stage("Delete github release") {
                    docker.image(ci_image).inside("--entrypoint=") {
                        run_in_ash("gh release delete --repo ${kube_agent_github_repo} -y v${this_version}");
                    }
                }
            }
            else {
                Utils.markStageSkippedForConditional("Delete github release");
            }
            stage("Create github release, upload helm chart artifact") {
                docker.image(ci_image).inside("--entrypoint=") {
                    // Note: see more details on the "gh" tool in the Dockerfile of the CI image.
                    run_in_ash("gh release create --repo=${kube_agent_github_repo} --target=${commit_sha} --notes='' --title=v${this_version} v${this_version} dist-helm/checkmk-kube-agent-helm-${this_version}.tgz");
                }
            }
        }

        if (method == "rebuild_version") {
            Utils.markStageSkippedForConditional("Update helm repo index");
        }
        else {
            stage("Update helm repo index") {
                withCredentials([sshUserPrivateKey(credentialsId: "jenkins-gerrit-fips-compliant-ssh-key", keyFileVariable: 'keyfile')]) {
                    withEnv(["GIT_SSH_COMMAND=ssh -o \"StrictHostKeyChecking no\" -i ${keyfile} -l jenkins"]) {
                        sh("git fetch origin ${github_pages_branch}");
                        sh("git checkout ${github_pages_branch}");
                        sh("git pull");
                    }
                }

                withCredentials([sshUserPrivateKey(credentialsId: "release", keyFileVariable: 'keyfile')]) {
                    withEnv(["GIT_SSH_COMMAND=ssh -o \"StrictHostKeyChecking no\" -i ${keyfile} -l release"]) {
                        // The git reference clones have to be mounted to the container in order to make the
                        // git actions work. Without mounting those parsing HEAD fails.
                        docker.image(ci_image).inside("-v /home/jenkins/git_reference_clones/checkmk_kube_agent.git/:/home/jenkins/git_reference_clones/checkmk_kube_agent.git/:ro --entrypoint=") {
                            run_in_ash("mv dist-helm/checkmk-kube-agent-helm-${this_version}.tgz ${workspace_dir}");

                            if (fileExists("${helm_repo_index_file}")) {
                                merge_index_cmd = "--merge ${helm_repo_index_file}";
                            }
                            else {
                                merge_index_cmd = "";
                            }

                            run_in_ash("helm repo index ${workspace_dir} ${merge_index_cmd} --url ${kube_agent_github_url}/releases/download/v${this_version}");
                            run_in_ash("git add ${helm_repo_index_file}");
                            run_in_ash("git commit ${helm_repo_index_file} -m 'Add helm chart version ${this_version}'");
                            run_in_ash("git push origin ${github_pages_branch}");
                        }
                    }
                }

                // This can be deleted if the push to github can be triggered some other way (see CMK-9584)
                withCredentials([file(credentialsId: github_ssh_credential_id, variable: 'keyfile')]) {
                    withEnv(["GIT_SSH_COMMAND=ssh -o \"StrictHostKeyChecking no\" -i ${keyfile}"]) {
                        docker.image(ci_image).inside("--entrypoint=") {
                            run_in_ash("git push github ${github_pages_branch}");
                        }
                    }
                }

                // Back to the non-github-pages branch
                sh("git checkout ${this_branch}");
            }
        }
    }
}

return this;
