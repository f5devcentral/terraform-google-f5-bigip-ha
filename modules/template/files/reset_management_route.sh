#!/bin/sh
#
# This script is intended to be executed on every boot to ensure the management default gateway is set correctly. This
# is to address a bug (https://cdn.f5.com/product/bugtracker/ID930905.html) present in older versions of BIG-IP by
# resetting the default management route through VPC gateway on boot (see https://support.f5.com/csp/article/K85730674).
#
# NOTE: This bug has been fixed in recent BIG-IP releases; this script is included in common onboarding just in case a
# deployment has to use pre-fixed BIG-IP release since it has a minimal impact on BIG-IP startup time regardless of
# necessity.
#
# Script is expected to be safe to re-execute as needed, and should be triggered through systemd via
# f5-gce-reset-management-route.service unit that is enabled on every boot after initial onboarding is complete.
#
# Environment variables can be set to change default values or influence behavior:
#
# The zero-based index into network interfaces that is expected to be bound as BIG-IP management interface if the VM has
# multiple network interfaces. Default is 1 (i.e. eth1 is assumed to be management interface on multi-NIC VE) for
# consistency with published documents.
MGMT_INTERFACE="${MGMT_INTERFACE:-1}"

info()
{
    echo "$0: INFO: $*" >&2
}

info "Management route reset handler: starting, waiting for BIG-IP to be ready"

# shellcheck source=/dev/null
. /usr/lib/bigstart/bigip-ready-functions
wait_bigip_ready

nic_count="$(curl -sf --retry 20 -H "Metadata-Flavor: Google" "http://169.254.169.254/computeMetadata/v1/instance/network-interfaces/?recursive=true" | jq --raw-output '.|length')"
nic_count="${nic_count:-1}"
if [ "${nic_count}" -gt 1 ]; then
    target_gateway="$(curl -sf --retry 20 -H "Metadata-Flavor: Google" "http://169.254.169.254/computeMetadata/v1/instance/network-interfaces/${MGMT_INTERFACE}/gateway")"
    target_mtu="$(curl -sf --retry 20 -H "Metadata-Flavor: Google" "http://169.254.169.254/computeMetadata/v1/instance/network-interfaces/${MGMT_INTERFACE}/mtu")"
    current_gw="$(tmsh list sys management-route default gateway | awk 'NR==2 { print $2 }')"
    while [ "${current_gw}" != "${target_gateway}" ]; do
        info "Management route reset handler: setting default gateway to ${target_gateway} with MTU ${target_mtu}; was ${current_gw}."
        tmsh delete sys management-route default
        tmsh create sys management-route default gateway "${target_gateway}" mtu "${target_mtu}"
        tmsh save /sys config
        current_gw="$(tmsh list sys management-route default gateway | awk 'NR==2 { print $2 }')"
    done
    info "Management route reset handler: complete"
else
    info "Management route reset handler: nothing to do"
fi
