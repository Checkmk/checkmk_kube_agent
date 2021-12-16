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
        do_it();
    }
}

def do_it() {
    def IMAGES;
    def PROJECT_VERSION;
    def DOCKER_GROUP_ID = sh(script: "getent group docker | cut -d: -f3", returnStdout: true);
    stage("check out") {
        checkout(scm);
    }
    stage("build source and wheel package") {
        docker.build("checkmk-kube-agent-ci", "-f docker/ci/Dockerfile .");
        docker.image("checkmk-kube-agent-ci:latest").inside("-v /var/run/docker.sock:/var/run/docker.sock --group-add=${DOCKER_GROUP_ID} --entrypoint=") {
            PROJECT_VERSION = sh(script: "#!/bin/ash\nmake print-version", returnStdout: true).toString().trim();
            sh("#!/bin/ash\nmake release-image");
        }
    }
    stage("build dev image") {
        CLUSTER_COLLECTOR_IMAGE = docker.build("checkmk-cluster-collector-dev", "--target=dev --build-arg PACKAGE_VERSION=${PROJECT_VERSION} -f docker/cluster_collector/Dockerfile .");
        NODE_COLLECTOR_IMAGE = docker.build("checkmk-node-collector-dev", "--target=dev --build-arg PACKAGE_VERSION=${PROJECT_VERSION} -f docker/node_collector/Dockerfile .");
        IMAGES = [CLUSTER_COLLECTOR_IMAGE, NODE_COLLECTOR_IMAGE];
    }
    stage("lint python: bandit") {
        run_target(IMAGES, "lint-python/bandit", "--entrypoint=");
    }
    stage("lint python: format") {
        run_target(IMAGES, "lint-python/format", "--entrypoint=");
    }
    stage("lint python: pylint") {
        run_target(IMAGES, "lint-python/pylint", "--entrypoint=");
    }
    stage("python unit and doc test") {
        run_target(IMAGES, "test-unit", "--entrypoint=");
    }
}

def run_target(images, target, docker_args) {
    images.each { image ->
        image.inside(docker_args) {
            sh("#!/bin/ash\nmake ${target}");
        }
    }
}
