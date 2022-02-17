import java.text.SimpleDateFormat

currentBuild.description = '\nBuilding the Kubernetes Agent\n'

def NODE = ''
withFolderProperties{
    NODE = env.BUILD_NODE
}

// TODO: Duplicate code from checkmk repo -> move to common repo
def get_branch(scm) {
    def BRANCH = scm.branches[0].name.replaceAll("/","-")
    return BRANCH
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
    ])
])

def RELEASE_BUILD
def DOCKER_TAG_PREFIX
def DOCKER_TAG_SUFFIX
def BRANCH = get_branch(scm)


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

timeout(time: 12, unit: 'HOURS') {
    node(NODE) {
        stage('Checkout Sources') {
            checkout(scm)
        }

        // TODO: at least consolidate in this repo...
        def DOCKER_GROUP_ID = sh(script: "getent group docker | cut -d: -f3", returnStdout: true);
        docker.build("checkmk-kube-agent-ci", "-f docker/ci/Dockerfile .");

        if (RELEASE_BUILD) {
            stage('Calculate Version') {
                if (METHOD != "rebuild_version") {
                    docker.image("checkmk-kube-agent-ci:latest").inside("-v /var/run/docker.sock:/var/run/docker.sock --group-add=${DOCKER_GROUP_ID} --entrypoint=") {
                        VERSION = run_in_ash("METHOD=${METHOD} make print-bumped-version", true).toString().trim();
                    }
                }
                else {
                    VERSION = VERSION
                }
            }

            stage("Create or switch to tag") {
                withCredentials([sshUserPrivateKey(credentialsId: "release", keyFileVariable: 'keyfile')]) {
                    withEnv(["GIT_AUTHOR_NAME=Checkmk release system",
                             "GIT_AUTHOR_EMAIL='feedback@check-mk.org'",
                             "GIT_SSH_COMMAND=ssh -o \"StrictHostKeyChecking no\" -i ${keyfile} -l release",
                             "GIT_SSH_VARIANT=ssh",
                             "GIT_COMMITTER_NAME=Checkmk release system",
                             "GIT_COMMITTER_EMAIL=feedback@check-mk.org"]) {
                        docker.image("checkmk-kube-agent-ci:latest").inside("-v /var/run/docker.sock:/var/run/docker.sock --group-add=${DOCKER_GROUP_ID} --entrypoint=") {
                            run_in_ash("./ci/jenkins/scripts/tagging.sh ${VERSION} ${METHOD} ${BRANCH}")
                        }
                    }
                }
            }
        }


        stage("Build source and wheel package") {
            docker.image("checkmk-kube-agent-ci:latest").inside("-v /var/run/docker.sock:/var/run/docker.sock --group-add=${DOCKER_GROUP_ID} --entrypoint=") {
                run_in_ash("make dist")
            }
        }
        stage("Build Images") {
            docker.image("checkmk-kube-agent-ci:latest").inside("-v /var/run/docker.sock:/var/run/docker.sock --group-add=${DOCKER_GROUP_ID} --entrypoint=") {
                run_in_ash("DOCKER_TAG_PREFIX=${DOCKER_TAG_PREFIX} DOCKER_TAG_SUFFIX=${DOCKER_TAG_SUFFIX} make release-image")
            }

        stage('Push Images') {
            withCredentials([
                    usernamePassword(credentialsId: '11fb3d5f-e44e-4f33-a651-274227cc48ab', passwordVariable: 'DOCKER_PASSPHRASE', usernameVariable: 'DOCKER_USERNAME')]) {
                    docker.image("checkmk-kube-agent-ci:latest").inside("-v /var/run/docker.sock:/var/run/docker.sock --group-add=${DOCKER_GROUP_ID} --entrypoint=") {
                        run_in_ash('echo \"${DOCKER_PASSPHRASE}\" | docker login -u ${DOCKER_USERNAME} --password-stdin')
                        run_in_ash("DOCKER_TAG_PREFIX=${DOCKER_TAG_PREFIX} DOCKER_TAG_SUFFIX=${DOCKER_TAG_SUFFIX} make push-images")
                    }
                }
            }
        }
    }
}
