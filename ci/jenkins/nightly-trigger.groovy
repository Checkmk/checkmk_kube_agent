#!groovy

/// file: nightly-trigger.groovy

def main() {
    stage('Trigger image build') {
        build(
            job: "./build-k8-agent",
            parameters: [
                [$class: 'StringParameterValue', name: 'METHOD', value: 'daily'],
                [$class: 'BooleanParameterValue', name: 'PUSH_TO_DOCKERHUB', value: true],
            ],
        );
    }
}

return this;
