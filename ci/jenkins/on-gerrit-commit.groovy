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
    stage("check out") {
        checkout(scm);
    }
    stage("build source and wheel package") {
        sh("make release-image");
    }
    stage("build dev image") {
        CLUSTER_COLLECTOR_IMAGE = docker.build("checkmk-cluster-collector-dev", "--target=dev -f docker/cluster_collector/Dockerfile .");
        NODE_COLLECTOR_IMAGE = docker.build("checkmk-node-collector-dev", "--target=dev -f docker/node_collector/Dockerfile .");
        IMAGES = [CLUSTER_COLLECTOR_IMAGE, NODE_COLLECTOR_IMAGE];
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
