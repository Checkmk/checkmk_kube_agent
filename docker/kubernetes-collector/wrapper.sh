#!/bin/sh

# the checkmk linux agent checks if it's running inside a docker or lxc
# container. the openwrt agent does not have those checks. we have placed some
# comments in the openwrt agent to make sure we get informed if this will be
# added.

# don't execute the main function of check_mk_agent, we call only certain sections
MK_SOURCE_AGENT=1
. /usr/local/bin/check_mk_agent.openwrt

echo "<<<check_mk>>>"
echo "Version: VERSION_CMK"
echo "AgentOS: kube VERSION_AGENT"

main_setup
section_kernel
section_uptime
section_cpu
section_mem
section_diskstat
section_df
set_up_profiling
section_checkmk_agent_plugins
run_plugins
