#!/bin/sh

# the checkmk linux agent checks if it's running inside a docker or lxc
# container. the openwrt agent does not have those checks. we have placed some
# comments in the openwrt agent to make sure we get informed if this will be
# added.

# don't execute the main function of check_mk_agent, we call only certain sections
MK_SOURCE_AGENT=1
. /usr/local/bin/check_mk_agent.openwrt
. /usr/local/bin/mk_inventory.linux

echo "<<<check_mk>>>"
echo "Version: VERSION_CMK"
echo "AgentOS: kube VERSION_AGENT"

main_setup
# check_mk_agent.openwrt
section_kernel
section_uptime
section_cpu
section_mem
section_diskstat
section_df
# agent plugins (run via agent)
set_up_profiling
section_checkmk_agent_plugins
run_plugins
# sections from mk_inventory
section_lnx_cpuinfo
section_lnx_uname
section_lnx_block_devices
section_lnx_video
# some sections have non-zero exit codes due to a 'return' without an explicit
# exit code, which implies that the section is not relevant for the host
exit 0 # ignore the return code of the last section
