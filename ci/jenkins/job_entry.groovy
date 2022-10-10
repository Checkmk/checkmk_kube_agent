#!groovy

/// file: job_entry.groovy

/// This is the branch specific checkmk_kube_agent main entry point. It exists to
/// avoid redundant code in the actual job definition files and to be able
/// to provide a standard environment for all checkmk_kube_agent jobs

def main(job_definition_file) {
    sh_output = { cmd ->
        try {
            return sh(script: cmd, returnStdout: true).trim();
        } catch (Exception exc) {
            print("WARNING: Executing ${cmd} returned non-zero: ${exc}");
        }
        return "";
    };
    
    ash = { cmd ->
        sh(script: "#!/bin/ash\n${cmd}", returnStdout: false);
    }
    
    ash_output = { cmd ->
        return sh(script: "#!/bin/ash\n${cmd}", returnStdout: true).toString().trim();
    }

    /// TODO: error handling!
    dir("${checkout_dir}") {
        load("${checkout_dir}/${job_definition_file}").main();
    }
}
return this;

