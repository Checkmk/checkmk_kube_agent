#!groovy

/// file: nightly-trigger.groovy

properties([
    buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '7', numToKeepStr: '14')),
    pipelineTriggers([cron("0 5 * * *")])
])

def NODE = '';
withFolderProperties{
    NODE = env.BUILD_NODE;
}

node(NODE)
{
    stage('Trigger image build') {
        build(job: "./build-k8-agent",
            parameters: [
                [$class: 'StringParameterValue', name: 'METHOD', value: 'daily'],
                [$class: 'BooleanParameterValue', name: 'PUSH_TO_DOCKERHUB', value: true],
            ]
        )
    }
}
