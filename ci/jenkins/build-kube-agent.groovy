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

@Field
def RELEASE_BUILD=""
@Field
def DOCKER_TAG_PREFIX=""
@Field
def DOCKER_TAG_SUFFIX=""
def BRANCH = get_branch(scm)
@Field
def STAGE_PUSH_IMAGES = 'Push Images'

switch (METHOD) {
    case "daily":
        // A daily job
        RELEASE_BUILD = false
        def DATE_FORMAT = new SimpleDateFormat("yyyy.MM.dd")
        def DATE = new Date()
        DOCKER_TAG_SUFFIX = "_" + DATE_FORMAT.format(DATE)
        DOCKER_TAG_PREFIX = BRANCH
        break
    default:
        // A release job
        RELEASE_BUILD = true
        DOCKER_TAG_SUFFIX = ""
        DOCKER_TAG_PREFIX = ""
        break
}

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
validate_parameters_and_branch(METHOD, VERSION, BRANCH)

def main(BRANCH, METHOD, VERSION) {
        def COMMIT_SHA;
        // TODO: at least consolidate in this repo...
        def DOCKER_GROUP_ID = sh(script: "getent group docker | cut -d: -f3", returnStdout: true);
        def GITHUB_PAGES_BRANCH = "gh-pages";
        def KUBE_AGENT_GITHUB_REPO = "checkmk/checkmk_kube_agent";
        def KUBE_AGENT_GITHUB_URL = "https://github.com/${KUBE_AGENT_GITHUB_REPO}";
        def CI_IMAGE = "checkmk-kube-agent-ci";
        def HELM_REPO_INDEX_FILE="index.yaml";
        def GITHUB_SSH_CREDENTIAL_ID = "ssh_private_key_github_kubernetes";
        def GITHUB_TOKEN_CREDENTIAL_ID = "github-token-CheckmkCI-kubernetes";

        stage('Checkout Sources') {
            checkout(scm);
            sh("git clean -fd");
            sh("git remote add github git@github.com:${KUBE_AGENT_GITHUB_REPO}.git || true");
        }
        docker.build(CI_IMAGE, "--network=host -f docker/ci/Dockerfile .");

        stage('Validate Github credentials') {
            build(
            job: "./validate-release-credentials",
            )
        }

        if (RELEASE_BUILD) {
            stage('Calculate Version') {
                if (METHOD != "rebuild_version") {
                    docker.image(CI_IMAGE).inside("-v /var/run/docker.sock:/var/run/docker.sock --group-add=${DOCKER_GROUP_ID} --entrypoint=") {
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
                        docker.image(CI_IMAGE).inside("-v /var/run/docker.sock:/var/run/docker.sock --group-add=${DOCKER_GROUP_ID} --entrypoint=") {
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
            docker.image(CI_IMAGE).inside("-v /var/run/docker.sock:/var/run/docker.sock --group-add=${DOCKER_GROUP_ID} --entrypoint=") {
                run_in_ash("make dist")
            }
        }

        stage("Build Images") {
            docker.image(CI_IMAGE).inside("-v /var/run/docker.sock:/var/run/docker.sock --group-add=${DOCKER_GROUP_ID} --entrypoint=") {
                run_in_ash("DOCKER_TAG_PREFIX=${DOCKER_TAG_PREFIX} DOCKER_TAG_SUFFIX=${DOCKER_TAG_SUFFIX} make release-image")
            }

        }
        stage(STAGE_PUSH_IMAGES) {
            if (params.PUSH_TO_DOCKERHUB) {
                withCredentials([
                        usernamePassword(credentialsId: '11fb3d5f-e44e-4f33-a651-274227cc48ab', passwordVariable: 'DOCKER_PASSPHRASE', usernameVariable: 'DOCKER_USERNAME')]) {
                    docker.image(CI_IMAGE).inside("-v /var/run/docker.sock:/var/run/docker.sock --group-add=${DOCKER_GROUP_ID} --entrypoint=") {
                        run_in_ash('echo \"${DOCKER_PASSPHRASE}\" | docker login -u ${DOCKER_USERNAME} --password-stdin')
                        run_in_ash("DOCKER_TAG_PREFIX=${DOCKER_TAG_PREFIX} DOCKER_TAG_SUFFIX=${DOCKER_TAG_SUFFIX} make push-images")
                        }
                    }
                }
            else {
                Utils.markStageSkippedForConditional(STAGE_PUSH_IMAGES)
            }
        }
        if (RELEASE_BUILD) {
            withCredentials([usernamePassword(credentialsId: GITHUB_TOKEN_CREDENTIAL_ID, passwordVariable: 'GH_TOKEN', usernameVariable: "GH_USER")]) {
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
                                run_in_ash("git pull");
                                run_in_ash("mv dist-helm/checkmk-kube-agent-helm-${VERSION}.tgz ${WORKSPACE}");

                                if (fileExists("${HELM_REPO_INDEX_FILE}")) {
                                    merge_index_cmd = "--merge ${HELM_REPO_INDEX_FILE}"
                                }
                                else {
                                    merge_index_cmd = ""
                                }

                                run_in_ash("helm repo index ${WORKSPACE} ${merge_index_cmd} --url ${KUBE_AGENT_GITHUB_URL}/releases/download/v${VERSION}");
                                run_in_ash("git add ${HELM_REPO_INDEX_FILE}");
                                run_in_ash("git commit ${HELM_REPO_INDEX_FILE} -m 'Add helm chart version ${VERSION}'");
                                run_in_ash("git push origin ${GITHUB_PAGES_BRANCH}");
                            }
                        }
                    }
                    // This can be deleted if the push to github can be triggered some other way (see CMK-9584)
                    withCredentials([sshUserPrivateKey(credentialsId: GITHUB_SSH_CREDENTIAL_ID, keyFileVariable: 'keyfile')]) {
                        withEnv(["GIT_SSH_COMMAND=ssh -o \"StrictHostKeyChecking no\" -i ${keyfile}"]) {
                            docker.image(CI_IMAGE).inside("--entrypoint=") {
                                run_in_ash("git push github ${GITHUB_PAGES_BRANCH}");
                            }
                        }
                    }
                    sh("git checkout ${BRANCH}");
            }
        }
    }
}

timeout(time: 12, unit: 'HOURS') {
    node(NODE) {
        withEnv(["GIT_AUTHOR_NAME=Checkmk release system",
                 "GIT_AUTHOR_EMAIL='feedback@check-mk.org'",
                 "GIT_SSH_VARIANT=ssh",
                 "GIT_COMMITTER_NAME=Checkmk release system",
                 "GIT_COMMITTER_EMAIL=feedback@check-mk.org"]) {
            main(BRANCH, METHOD, VERSION);
        }
    }
}
