properties([
    buildDiscarder(logRotator(
        artifactDaysToKeepStr: '',
        artifactNumToKeepStr: '',
        daysToKeepStr: '7',
        numToKeepStr: '200')),
])

def NODE = '';

withFolderProperties {
    NODE = env.BUILD_NODE;
}

timeout(time: 12, unit: 'HOURS') {
    node(NODE) {
        ansiColor("xterm") {
            do_it();
        }
    }
}

def do_it() {
    def COLLECTOR_IMAGE;
    def PROJECT_PYVERSION;
    def CHECKMK_AGENT_VERSION;
    def DOCKER_GROUP_ID = sh(script: "getent group docker | cut -d: -f3", returnStdout: true);
    stage("check out") {
        checkout(scm);
    }
    stage("build source and wheel package") {
        docker.build("checkmk-kube-agent-ci", "-f docker/ci/Dockerfile .");
        docker.image("checkmk-kube-agent-ci:latest").inside("-v /var/run/docker.sock:/var/run/docker.sock --group-add=${DOCKER_GROUP_ID} --entrypoint=") {
            PROJECT_PYVERSION = sh(script: "#!/bin/ash\nmake print-project-pyversion", returnStdout: true).toString().trim();
            CHECKMK_AGENT_VERSION = sh(script: "#!/bin/ash\nmake print-checkmk-agent-version", returnStdout: true).toString().trim();
            sh("#!/bin/ash\nmake release-image");
        }
    }
    stage("build dev image") {
        COLLECTOR_IMAGE = docker.build("kubernetes-collector-dev", "--network=host --target=dev --build-arg GIT_HASH=${env.GIT_COMMIT} --build-arg PROJECT_PYVERSION=${PROJECT_PYVERSION} --build-arg CHECKMK_AGENT_VERSION=${CHECKMK_AGENT_VERSION} -f docker/kubernetes-collector/Dockerfile .");
    }
    stage("lint python: bandit") {
        run_target(COLLECTOR_IMAGE, "lint-python/bandit", "--entrypoint=");
    }
    stage("lint python: format") {
        run_target(COLLECTOR_IMAGE, "lint-python/format", "--entrypoint=");
    }
    stage("lint python: pylint") {
        run_target(COLLECTOR_IMAGE, "lint-python/pylint", "--entrypoint=");
    }
    stage("typing python: mypy") {
        run_target(COLLECTOR_IMAGE, "typing-python/mypy", "--entrypoint=");
    }
    stage("python unit and doc test") {
        run_target(COLLECTOR_IMAGE, "test-unit", "--entrypoint=");
    }
    stage("lint dockerfile: hadolint") {
        run_target(COLLECTOR_IMAGE, "lint-dockerfile/hadolint", "--entrypoint=");
    }
    stage("lint docker image: trivy") {
        run_target(COLLECTOR_IMAGE, "lint-docker-image/trivy", "-v /var/run/docker.sock:/var/run/docker.sock --group-add=${DOCKER_GROUP_ID} --entrypoint=");
    }
    stage("lint yaml: yamllint") {
        run_target(COLLECTOR_IMAGE, "lint-yaml/yamllint", "--entrypoint=");
    }
    stage("lint helm chart") {
        run_target(COLLECTOR_IMAGE, "lint-helm", "--entrypoint=");
    }
}

def run_target(image, target, docker_args) {
    image.inside(docker_args) {
        sh("#!/bin/ash\nmake ${target}");
    }
}
