import java.text.SimpleDateFormat

currentBuild.description = '\nBuilding the Kubernetes Agent\n'

def RELEASE_BUILD
def DOCKER_TAG_SUFFIX

if (METHOD == "rebuild_version" && VERSION == "") {
    error "You need to specify VERSION when rebuilding one."
}

switch (METHOD) {
    case "daily":
        // A daily job
        RELEASE_BUILD = false
        def DATE_FORMAT = new SimpleDateFormat("yyyy.MM.dd")
        def DATE = new Date()
        DOCKER_TAG_SUFFIX = "_" + DATE_FORMAT.format(DATE)
        break;
    default:
        // A release job
        RELEASE_BUILD = true
        DOCKER_TAG_SUFFIX = ""
        if (METHOD == "major") {
            error "We currently only do major releases manually by creating a new branch!"
        }
        break
}

// TODO: at least consolidate in this repo...
def DOCKER_GROUP_ID = sh(script: "getent group docker | cut -d: -f3", returnStdout: true);
docker.build("checkmk-kube-agent-ci", "-f docker/ci/Dockerfile .");

if (RELEASE_BUILD) {
    stage('Calculate Version') {
        if (METHOD != "rebuild_version") {
            docker.image("checkmk-kube-agent-ci:latest").inside("-v /var/run/docker.sock:/var/run/docker.sock --group-add=${DOCKER_GROUP_ID} --entrypoint=") {
                VERSION = sh(script: "#!/bin/ash\n METHOD=${METHOD} make print-bumped-version", returnStdout: true).toString().trim();
            }
        }
        else {
            VERSION = VERSION
        }
    }

    if (METHOD != "rebuild_version") {
        stage("Create tag and set version") {
            withCredentials([sshUserPrivateKey(credentialsId: "release", keyFileVariable: 'keyfile')]) {
                withEnv(["GIT_AUTHOR_NAME=Checkmk release system",
                         "GIT_AUTHOR_EMAIL='feedback@check-mk.org'",
                         "GIT_SSH_COMMAND=ssh -i ${keyfile} -l release",
                         "GIT_SSH_VARIANT=ssh",
                         "GIT_COMMITTER_NAME=Checkmk release system",
                         "GIT_COMMITTER_EMAIL=feedback@check-mk.org"]) {
                    sh("./ci/jenkins/scripts/make_tags.sh ${VERSION} ${METHOD}")
                }
            }
        }
    }
}


stage("Build source and wheel package") {
    docker.image("checkmk-kube-agent-ci:latest").inside("-v /var/run/docker.sock:/var/run/docker.sock --group-add=${DOCKER_GROUP_ID} --entrypoint=") {
        PROJECT_VERSION = sh(script: "#!/bin/ash\nmake print-project-version", returnStdout: true).toString().trim();
        CHECKMK_AGENT_VERSION = sh(script: "#!/bin/ash\nmake print-checkmk-agent-version", returnStdout: true).toString().trim();
        println("Building collector in Version: " + PROJECT_VERSION + ", using checkmk agent in Version: " + CHECKMK_AGENT_VERSION)
        sh("#!/bin/ash\nmake dist");
    }
}
stage("Build Images") {
    COLLECTOR_IMAGE = docker.build(
        "kubernetes-collector", 
        "--target=release --tag 'version:${PROJECT_VERSION}' --build-arg PROJECT_VERSION=${PROJECT_VERSION} --build-arg CHECKMK_AGENT_VERSION=${CHECKMK_AGENT_VERSION} -f docker/kubernetes-collector/Dockerfile .");
    // TODO: The name for the cadvisor image is not clear yet - needs to be defined by Martin H. 
    CADVISOR_IMAGE = docker.build(
        "cadvisor", 
        "--target=release --tag 'version:${PROJECT_VERSION}' --build-arg PROJECT_VERSION=${PROJECT_VERSION} -f docker/cadvisor/Dockerfile .");
    IMAGES = [COLLECTOR_IMAGE, CADVISOR_IMAGE];
}

stage('Push Images') {
    docker.withRegistry(DOCKER_REGISTRY, 'nexus') {
        IMAGES.each {IMAGE -> IMAGE.push("v" + PROJECT_VERSION + DOCKER_TAG_SUFFIX)}
    }

}

