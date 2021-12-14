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
}
