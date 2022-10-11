#!groovy

/// file: build-kube-agent.groovy

import java.text.SimpleDateFormat
import org.jenkinsci.plugins.pipeline.modeldefinition.Utils
import groovy.transform.Field


def validate_parameters_and_branch(method, version, branch) {
    if (method == "rebuild_version" && version == "") {
        error "You need to specify VERSION when rebuilding one!";
    }
    if (method == "major") {
        error "We currently only do major releases manually by creating a new branch!";
    }
    if (branch == "main" && method != "daily") {
        error "We currently only create daily builds from branch main!";
    }
}

def determine_docker_tag(is_release_build, version) {
    if (is_release_build) {
        return version;
    }
    return "main_${(new SimpleDateFormat("yyyy.MM.dd")).format(new Date())}";
}

def main() {
    // FIXME apply where needed
    withEnv(["GIT_AUTHOR_NAME=Checkmk release system",
             "GIT_AUTHOR_EMAIL='feedback@check-mk.org'",
             "GIT_SSH_VARIANT=ssh",
             "GIT_COMMITTER_NAME=Checkmk release system",
             "GIT_COMMITTER_EMAIL=feedback@check-mk.org"]) {

        def kube_agent_github_repo = "tribe29/checkmk_kube_agent";
        def kube_agent_github_url = "https://github.com/${kube_agent_github_repo}";
        def github_pages_branch = "gh-pages";
        def ci_image_name = "checkmk-kube-agent-ci";
        def helm_repo_index_file = "index.yaml";

        def branch = scm.branches[0].name;
        def method = params.METHOD;
        def is_release_build = (method != "daily");
        def push_to_dockerhub = params.PUSH_TO_DOCKERHUB;
        def docker_image_tag = determine_docker_tag(is_release_build, version);

        def mount_docker_sock = "-v /var/run/docker.sock:/var/run/docker.sock";
        def add_docker_group_id = "--group-add=${sh_output('getent group docker | cut -d: -f3')}";
        def docker_args = "--entrypoint=";
        def git_commit_id;

        stage("Setup workspace and git clone") {
            sh("git clean -fd");
            sh("git remote add github git@github.com:${kube_agent_github_repo}.git || true");
        }

        def ci_image = { name ->
            stage("Build CI image") {
                return docker.build(name, "--network=host -f docker/ci/Dockerfile .");
            }
        }(ci_image_name);
        
        def version = {
            stage('Calculate Version') {
                if (is_release_build && method != "rebuild_version") {
                    ci_image.inside("${docker_args}") {
                        return ash_output("METHOD=${method} make print-bumped-version");
                    }
                }
                return params.VERSION;
            }
        }();

        print(
            """
            |===== CONFIGURATION ===============================
            |VERSION:                 |${params.VERSION}│
            |METHOD:                  |${params.METHOD}│
            |PUSH_TO_DOCKERHUB:       |${params.PUSH_TO_DOCKERHUB}│
            |branch:                  |${branch}│
            |version:                 |${version}│
            |method:                  |${method}│
            |kube_agent_github_repo:  |${kube_agent_github_repo}│
            |kube_agent_github_url:   |${kube_agent_github_url}│
            |github_pages_branch:     |${github_pages_branch}│
            |ci_image_name:           |${ci_image_name}│
            |push_to_dockerhub:       |${push_to_dockerhub}│
            |is_release_build:        |${is_release_build}│
            |docker_image_tag:        |${docker_image_tag}│
            |===================================================
            """.stripMargin());

        validate_parameters_and_branch(method, version, branch);

        conditional_stage("Create or switch to tag", is_release_build) {
            with_git_ssh_command("release") {
                ci_image.inside("${docker_args}") {
                    // FIXME 
                    ash("echo RUNCMD ci/jenkins/scripts/tagging.sh ${version} ${method} ${branch}");
                }
            }
            git_commit_id = sh_output("git rev-list -n 1 v${version}");
        }
        
        // The tag must exist on github in order to be able to use it to create a github release later
        // This can be deleted if the push to github can be triggered some other way (see CMK-9584)
        conditional_stage("Push to github", is_release_build && method != "rebuild_version") {
            with_git_ssh_command("ssh_private_key_lisa_github") {
                ci_image.inside("${docker_args}") {
                    // FIXME
                    ash("echo RUNCMD git push --tags github ${branch}");
                }
            }
        }

        stage("Build source and wheel package") {
            ci_image.inside("${docker_args}") {
                ash("make dist");
            }
        }

        stage("Build Images") {
            ci_image.inside("${mount_docker_sock} ${add_docker_group_id} ${docker_args}") {
                ash("make DOCKER_IMAGE_TAG=${docker_image_tag} release-image");
            }
        }
        
        conditional_stage("Push Images", push_to_dockerhub) {
            withCredentials([
                usernamePassword(
                    credentialsId: '11fb3d5f-e44e-4f33-a651-274227cc48ab',
                    passwordVariable: 'DOCKER_PASSPHRASE',
                    usernameVariable: 'DOCKER_USERNAME')]) {
                ci_image.inside("${mount_docker_sock} ${add_docker_group_id} ${docker_args}") {
                    ash("echo '\$DOCKER_PASSPHRASE' | docker login -u '\$DOCKER_USERNAME' --password-stdin");
                    // FIXME 
                    ash("echo RUNCMD make DOCKER_IMAGE_TAG=${docker_image_tag} push-images");
                }
            }
        }

        withCredentials([
            usernamePassword(
                credentialsId: "github-token-lisa",
                passwordVariable: 'GH_TOKEN',
                usernameVariable: "GH_USER")]) {
            
            conditional_stage("Delete github release", is_release_build && method == "rebuild_version") {
                ci_image.inside("${docker_args}") {
                    // FIXME 
                    ash("echo RUNCMD gh release delete --repo ${kube_agent_github_repo} -y v${version}")
                }
            }
            
            conditional_stage("Create github release, upload helm chart artifact", is_release_build) {
                ci_image.inside("${docker_args}") {
                    // Note: see more details on the "gh" tool in the Dockerfile of the CI image.
                    ash("""
                        echo RUNCMD gh release create \
                            --repo=${kube_agent_github_repo} \
                            --target=${git_commit_id} \
                            --notes='' \
                            --title=v${version} \
                            v${version} \
                            dist-helm/checkmk-kube-agent-helm-${version}.tgz
                    """);
                }
            }
        }
        
        conditional_stage("Update helm repo index", is_release_build && method != "rebuild_version") {
            sh("git checkout ${github_pages_branch}");
            with_git_ssh_command("release") {
                ci_image.inside("${docker_args}") {
                    // FIXME 
                    ash("""
                        echo RUNCMD scripts/update-helm-repo.sh \
                            --github-pages ${github_pages_branch} \
                            --helm-repo-index ${helm_repo_index_file} \
                            --url ${kube_agent_github_repo} \
                            --version ${version}""");
                }
            }
            
            // This can be deleted if the push to github can be triggered
            // some other way (see CMK-9584)
            with_git_ssh_command("ssh_private_key_lisa_github") {
                ci_image.inside("${docker_args}") {
                    ash("git checkout ${github_pages_branch}");
                    // FIXME 
                    ash("echo RUNCMD git push github ${github_pages_branch}");
                    sh("git checkout ${branch}");
                }
            }
        }
    }
}
return this;



