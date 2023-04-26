import java.text.SimpleDateFormat
import org.jenkinsci.plugins.pipeline.modeldefinition.Utils
import groovy.transform.Field

currentBuild.description = '\nBuilding the Kubernetes Agent\n'

def NODE = ''
withFolderProperties{
    NODE = env.BUILD_NODE
}

// TODO: Duplicate code from checkmk repo -> move to common repo
def get_branch(scm) {
    return scm.branches[0].name
}

properties([
    buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '7', numToKeepStr: '14')),
    parameters([
        choice(choices: ['daily', 'beta', 'minor', 'patch', 'rebuild_version', 'finalize_version'], name: 'METHOD',
                description: '<b>Choose the method the build job should follow.</b><br>' +
                        'daily -> Create a build on the current git state<br>' +
                        'minor/patch -> Create a release build with taging and incrementing the version<br>' +
                        'rebuild_version -> Try to rebuild of an already created release. You need to give a version ' +
                        'in the format of Major.Minor.Patch for this method.'),
        string(name: 'VERSION', defaultValue: '', description:
                'Set this in combination with "rebuild_version" in order to rebuild a specific version' ),
        booleanParam(name: 'PUSH_TO_DOCKERHUB', defaultValue: false, description: 'Set to true if you want to push the images to dockerhub.'),
    ])
])

def run_in_ash(command, get_stdout=false) {
    ash_command = "#!/bin/ash\n" + command
    return sh(script: "${ash_command}", returnStdout: get_stdout)
}

def validate_parameters_and_branch(method, version, branch) {
    // This function validates the parameters in combination with the branch to be built from
    if (method == "rebuild_version" && version == "") error "You need to specify VERSION when rebuilding one!"
    if (method == "major") error "We currently only do major releases manually by creating a new branch!"
    if (branch == "main" && method != "daily") error "We currently only create daily builds from branch main!"
}

def determine_docker_tag(is_release_build, version) {
    if (is_release_build) {
        DOCKER_TAG = VERSION;
    }
    else {
        DATE = new Date();
        DATE_FORMAT = new SimpleDateFormat("yyyy.MM.dd");
        DATE_STRING = DATE_FORMAT.format(DATE);
        DOCKER_TAG = "main_${DATE_STRING}";

    }
    return DOCKER_TAG
}

def main(BRANCH, METHOD, VERSION, IS_RELEASE_BUILD) {
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
        ** example was https://github.com/tribe29/checkmk_kube_agent/commits/gh-pages (add helm chart version 1.1.0)
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
        * the releases can be verified here https://github.com/tribe29/checkmk_kube_agent/releases

        ## Troubleshoot Github Pages
        * the steps in update-helm-repo can be followed manually
        * KNOWN PROBLEM: the gh command line tool does not recognize files which are located in the /tmp (potentially
        also others) directory
        * see General Troubleshoot (above) if github push attempt fails

        */
        def COMMIT_SHA;
        // TODO: at least consolidate in this repo...
        def DOCKER_GROUP_ID = sh(script: "getent group docker | cut -d: -f3", returnStdout: true);
        def GITHUB_PAGES_BRANCH = "gh-pages";
        def KUBE_AGENT_GITHUB_REPO = "tribe29/checkmk_kube_agent";
        def KUBE_AGENT_GITHUB_URL = "https://github.com/${KUBE_AGENT_GITHUB_REPO}";
        def CI_IMAGE = "checkmk-kube-agent-ci";
        def HELM_REPO_INDEX_FILE="index.yaml";
        def STAGE_PUSH_IMAGES = 'Push Images'

        stage('Checkout Sources') {
            checkout(scm);
            sh("git clean -fd");
            sh("git remote add github git@github.com:${KUBE_AGENT_GITHUB_REPO}.git || true");
        }
        docker.build(CI_IMAGE, "--network=host -f docker/ci/Dockerfile .");

        if (IS_RELEASE_BUILD) {
            stage('Calculate Version') {
                if (METHOD != "rebuild_version") {
                    docker.image(CI_IMAGE).inside("--entrypoint=") {
                        VERSION = run_in_ash("METHOD=${METHOD} make print-bumped-version", true).toString().trim();
                    }
                }
                else {
                    VERSION = VERSION;
                }
            }

            stage("Create or switch to tag") {
                withCredentials([sshUserPrivateKey(credentialsId: "release", keyFileVariable: 'keyfile')]) {
                    withEnv(["GIT_SSH_COMMAND=ssh -o \"StrictHostKeyChecking no\" -i ${keyfile} -l release"]) {
                        docker.image(CI_IMAGE).inside("--entrypoint=") {
                            run_in_ash("./ci/jenkins/scripts/tagging.sh ${VERSION} ${METHOD} ${BRANCH}")
                        }
                    }
                }
                COMMIT_SHA = sh(script: "git rev-list -n 1 v${VERSION}", returnStdout: true).toString().trim();
            }
            // The tag must exist on github in order to be able to use it to create a github release later
            // This can be deleted if the push to github can be triggered some other way (see CMK-9584)
            if (METHOD != "rebuild_version") {
                stage("Push to github") {
                    withCredentials([file(credentialsId: "ssh_private_key_github_kubernetes", variable: 'keyfile')]) {
                        withEnv(["GIT_SSH_COMMAND=ssh -o \"StrictHostKeyChecking no\" -i ${keyfile}"]) {
                            docker.image(CI_IMAGE).inside("--entrypoint=") {
                                run_in_ash("git push --tags github ${BRANCH}")
                            }
                        }
                    }
                }
            }
            else {
                Utils.markStageSkippedForConditional("rebuild_version")
            }
        }

        stage("Build source and wheel package") {
            docker.image(CI_IMAGE).inside("--entrypoint=") {
                run_in_ash("make dist")
            }
        }

        stage("Build Images") {
            DOCKER_IMAGE_TAG = determine_docker_tag(IS_RELEASE_BUILD, VERSION);
            docker.image(CI_IMAGE).inside("-v /var/run/docker.sock:/var/run/docker.sock --group-add=${DOCKER_GROUP_ID} --entrypoint=") {
                run_in_ash("make DOCKER_IMAGE_TAG=${DOCKER_IMAGE_TAG} release-image")
            }

        }
        stage(STAGE_PUSH_IMAGES) {
            if (params.PUSH_TO_DOCKERHUB) {
                withCredentials([
                        usernamePassword(credentialsId: '11fb3d5f-e44e-4f33-a651-274227cc48ab', passwordVariable: 'DOCKER_PASSPHRASE', usernameVariable: 'DOCKER_USERNAME')]) {
                    docker.image(CI_IMAGE).inside("-v /var/run/docker.sock:/var/run/docker.sock --group-add=${DOCKER_GROUP_ID} --entrypoint=") {
                        run_in_ash('echo \"${DOCKER_PASSPHRASE}\" | docker login -u ${DOCKER_USERNAME} --password-stdin')
                        run_in_ash("make DOCKER_IMAGE_TAG=${DOCKER_IMAGE_TAG} push-images")
                        }
                    }
                }
            else {
                Utils.markStageSkippedForConditional(STAGE_PUSH_IMAGES)
            }
        }
        if (IS_RELEASE_BUILD) {
            withCredentials([usernamePassword(credentialsId: "github-token-lisa", passwordVariable: 'GH_TOKEN', usernameVariable: "GH_USER")]) {
                if (METHOD == "rebuild_version") {
                    stage("Delete github release") {
                        docker.image(CI_IMAGE).inside("--entrypoint=") {
                                run_in_ash("gh release delete --repo ${KUBE_AGENT_GITHUB_REPO} -y v${VERSION}")
                        }
                    }
                }
                else {
                    Utils.markStageSkippedForConditional("Delete github release")
                }
                stage("Create github release, upload helm chart artifact") {
                    docker.image(CI_IMAGE).inside("--entrypoint=") {
                        // Note: see more details on the "gh" tool in the Dockerfile of the CI image.
                        run_in_ash("gh release create --repo=${KUBE_AGENT_GITHUB_REPO} --target=${COMMIT_SHA} --notes='' --title=v${VERSION} v${VERSION} dist-helm/checkmk-kube-agent-helm-${VERSION}.tgz")
                    }
                }
            }
            if (METHOD == "rebuild_version") {
                Utils.markStageSkippedForConditional("Update helm repo index")
            }
            else {
                stage("Update helm repo index") {
                    sh("git checkout ${GITHUB_PAGES_BRANCH}");
                    withCredentials([sshUserPrivateKey(credentialsId: "release", keyFileVariable: 'keyfile')]) {
                        withEnv(["GIT_SSH_COMMAND=ssh -o \"StrictHostKeyChecking no\" -i ${keyfile} -l release"]) {
                            docker.image(CI_IMAGE).inside("--entrypoint=") {
                                run_in_ash("scripts/update-helm-repo.sh --github-pages ${GITHUB_PAGES_BRANCH} --helm-repo-index ${HELM_REPO_INDEX_FILE} --url ${KUBE_AGENT_GITHUB_URL} --version ${VERSION}");
                            }
                        }
                    }
                    // This can be deleted if the push to github can be triggered some other way (see CMK-9584)
                    withCredentials([sshUserPrivateKey(credentialsId: "ssh_private_key_lisa_github", keyFileVariable: 'keyfile')]) {
                        withEnv(["GIT_SSH_COMMAND=ssh -o \"StrictHostKeyChecking no\" -i ${keyfile}"]) {
                            docker.image(CI_IMAGE).inside("--entrypoint=") {
                                run_in_ash("git checkout ${GITHUB_PAGES_BRANCH}");
                                run_in_ash("git push github ${GITHUB_PAGES_BRANCH}");
                                sh("git checkout ${BRANCH}");
                            }
                        }
                    }
            }
        }
    }
}

switch (METHOD) {
    case "daily":
        IS_RELEASE_BUILD = false
        break
    default:
        IS_RELEASE_BUILD = true
        break
}

def BRANCH = get_branch(scm);

validate_parameters_and_branch(METHOD, VERSION, BRANCH)

timeout(time: 12, unit: 'HOURS') {
    node(NODE) {
        withEnv(["GIT_AUTHOR_NAME=Checkmk release system",
                 "GIT_AUTHOR_EMAIL='feedback@check-mk.org'",
                 "GIT_SSH_VARIANT=ssh",
                 "GIT_COMMITTER_NAME=Checkmk release system",
                 "GIT_COMMITTER_EMAIL=feedback@check-mk.org"]) {
            main(BRANCH, METHOD, VERSION, IS_RELEASE_BUILD);
        }
    }
}
