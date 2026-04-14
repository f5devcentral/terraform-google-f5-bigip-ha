#!/bin/sh
# shellcheck disable=SC1083,SC2034
#
# Perform early onboarding of BIG-IP VE on Google Cloud - by default, the following steps will occur:
#
# 1. Configure management interface on eth1 if there are more than 1 network interfaces associated with the instance
# 2. Reboot to force management interface to be on eth1, if necessary
# 3. Download F5 BIG-IP Runtime-init package from F5 CDN, verify the download via checksum, and install the package
# 4. Execute runtime-init with configuration in /config/cloud/runtime-init-conf.yaml; up to three attempts will be made
#    to apply the configuration before failing
#
# Script is expected to be safe to re-execute as needed, and should be triggered through systemd via
# f5-gce-onboard.service unit.
#
# Environment variables can be set to change default values or influence behavior:
#
# The zero-based index into network interfaces that is expected to be bound as BIG-IP management interface if the VM has
# multiple network interfaces. Default is 1; i.e. eth1 is assumed to be management interface on multi-NIC VE for
# consistency with published documents.
MGMT_INTERFACE="${MGMT_INTERFACE:-1}"
# The URL of the F5 BIG-IP Runtime-init installer package; can be specified as an HTTP/HTTPS, FTP, GCS, or local file
# scheme (http://, https://, ftp://, gs://, or file://, respectively). Default value will be HTTPS URL of latest package
# on F5 CDN as of last update to this file. Set to SKIP to bypass download if runtime-init will not be used, or if the
# installer package is already on disk at /var/config/rest/downloads/f5-bigip-runtime-init.gz.run.
RUNTIME_INIT_URL="${RUNTIME_INIT_URL:-"https://cdn.f5.com/product/cloudsolutions/f5-bigip-runtime-init/v2.0.3/dist/f5-bigip-runtime-init-2.0.3-1.gz.run"}"
# The SHA-256 checksum value to use when validating the package download. Set to SKIP to bypass checksum validation.
RUNTIME_INIT_SHA256SUM="${RUNTIME_INIT_SHA256SUM:-"e38fabfee268d6b965a7c801ead7a5708e5766e349cfa6a19dd3add52018549a"}"
# Additional environment variables can be set to instruct curl to use a proxy for downloads (http_proxy, https_proxy,
# no_proxy, etc. - see curl documentation for details) or to add options to runtime-init installer
# (RUNTIME_INIT_INSTALLER_EXTRA_ARGS) and execution (RUNTIME_INIT_EXTRA_ARGS) commands.
# E.g. to turn off F5 runtime-init telemetry/error reporting
# RUNTIME_INIT_EXTRA_ARGS="--skip-telemetry"

# Log an info message
info()
{
    echo "$0: INFO: $*" >&2
}

# Log an error message and exit
error()
{
    echo "$0: ERROR: $*" >&2
    exit 1
}

# Set the VM guest attribute in f5-big-ip namespace to the provided value.
# $1 = key in the f5-big-ip namespace to set or delete
# $2 = value to set
set_status_attribute()
{
    # If we already know guest-attributes POST has failed, don't bother trying for subsequent calls
    if [ -z "${DO_NOT_SET_STATUS_ATTRIBUTES}" ]; then
        [ -n "${1}" ] || error "set_status_attributes: key is required"
        attempt=0
        while [ "${attempt}" -lt 10 ]; do
            if [ -n "${2}" ]; then
                status="$(curl -s --retry 20 -X PUT -H "Metadata-Flavor: Google" -o /dev/null -w "%{http_code}" -d "${2}" \
                    "http://169.254.169.254/computeMetadata/v1/instance/guest-attributes/f5-big-ip/${1}")"
                retval=$?
            else
                status="$(curl -s --retry 20 -X DELETE -H "Metadata-Flavor: Google" -o /dev/null -w "%{http_code}" \
                    "http://169.254.169.254/computeMetadata/v1/instance/guest-attributes/f5-big-ip/${1}")"
                retval=$?
            fi
            case "${status}" in
                "403")
                    info "set_status_attribute: setting guest-attribute values is prohibited on this instance"
                    DO_NOT_SET_STATUS_ATTRIBUTES="true"
                    break
                    ;;
                "200")
                    info "set_status_attribute: ${attempt}: Successfully updated guest-attribute 'f5-bigip-ip/${1}' with value '${2}'"
                    break
                    ;;
                *)
                    if [ -n "${2}" ]; then
                        info "set_status_attribute: ${attempt}: POST guest-attribute 'f5-bigip-ip/${1}' with value '${2}' unexpected response ${status} (exit code ${retval}); sleeping before retry"
                    else
                        info "set_status_attribute: ${attempt}: DELETE guest-attribute 'f5-bigip-ip/${1}' unexpected response ${status} (exit code ${retval}); sleeping before retry"
                    fi
                    sleep 5
                    attempt=$((attempt+1))
                    ;;
            esac
        done
        [ "${attempt}" -ge 10 ] && \
            info "set_status_attribute: ${attempt}: Failed to set guest-attribute 'f5-bigip-ip/${1}' to '${2}'"
    else
        retval=0
    fi
    # shellcheck disable=SC2086
    return ${retval}
}

# Return a bearer token for the VM service account to use with GCP APIs
auth_token()
{
    attempt=0
    while [ "${attempt}" -lt 10 ]; do
        auth_token="$(curl -sf --retry 20 -H "Metadata-Flavor: Google" http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token | jq --raw-output '.access_token')"
        retval=$?
        if [ "${retval}" -eq 0 ]; then
            echo "${auth_token}"
            break
        fi
        info "auth_token: ${attempt}: Curl failed with exit code ${retval}; sleeping before retry"
        sleep 15
        attempt=$((attempt+1))
    done
    [ "${attempt}" -ge 10 ] && \
        info "auth_token: ${attempt}: Failed to get an auth token from metadata server"
    # shellcheck disable=SC2086
    return ${retval}
}

# Download the remote resource to provided path
# $1 = URL
# $2 = output path
# $3+ are additional curl arguments
retry_download()
{
    url="$1"
    out="$2"
    shift
    shift
    attempt=0
    while [ "${attempt}" -lt 10 ]; do
        info "retry_download: ${attempt}: Downloading ${url} to ${out}"
        curl -sfL --retry 20 -o "${out}" "$@" "${url}"
        retval=$?
        [ "${retval}" -eq 0 ] && break
        info "retry_download: ${attempt}: Failed to download ${url}: exit code: ${retval}; sleeping before retrying"
        sleep 15
        attempt=$((attempt+1))
    done
    [ "${attempt}" -ge 10 ] && \
        info "retry_download: Failed to download from ${url}; giving up"
    # shellcheck disable=SC2086
    return ${retval}
}

# Download a file, recognizing GCS storage API requests and handle authentication as necessary.
# $1 = URL of remote file
# $2 = output path
download()
{
    mkdir -p "$(dirname "$2")" || \
        error "Error creating directory for $2; exit code $?"
    case "$1" in
        gs://*)
            gs_uri="$(printf '%s' "${1}" | jq --slurp --raw-input --raw-output 'split("/")[2:]|["https://storage.googleapis.com/download/storage/v1/b/", .[0], "/o/", (.[1:]|join("/")|@uri), "?alt=media"]|join("")')" || \
                error "Error creating JSON API URL from ${1}; exit code $?"
            auth_token="$(auth_token)" || error "Unable to get auth token"
            retry_download "${gs_uri}" "$2" -H "Authorization: Bearer ${auth_token}"
            ;;
        https://storage.googleapis.com/*)
            auth_token="$(auth_token)" || error "Unable to get auth token"
            retry_download "$1" "$2" -H "Authorization: Bearer ${auth_token}"
            ;;
        ftp://*|http://*|https://*)
            retry_download "$1" "$2"
            ;;
        file://*)
            cp "${1##file://}" "$2"
            ;;
        /*)
            cp "$1" "$2"
            ;;
        *)
            info "Unrecognized remote scheme for $1"
            false
            ;;
    esac
    return $?
}


mkdir -p /var/config/rest/downloads

info "Starting to onboard; waiting for BIG-IP to be ready"
set_status_attribute "onboarding" "in-progress"

# shellcheck source=/dev/null
. /usr/lib/bigstart/bigip-ready-functions
wait_bigip_ready

# Update sysdb values to recommendations and restart services; this should only happen once so that any overrides
# provided by runtime-init config are not changed.
if [ ! -f /config/cloud/.setDB ]; then
    info "Setting recommended system database values"
    set_status_attribute "set-db" "in-progress"
    /usr/bin/setdb provision.extramb 1000 || true
    /usr/bin/setdb provision.restjavad.extramb 1384 || /usr/bin/setdb restjavad.useextramb true || true
    /usr/bin/setdb iapplxrpm.timeout 300 || true
    /usr/bin/setdb icrd.timeout 180 || true
    /usr/bin/setdb restjavad.timeout 180 || true
    /usr/bin/setdb restnoded.timeout 180 || true
    bigstart restart restjavad
    bigstart restart restnoded
    touch /config/cloud/.setDB
    set_status_attribute "set-db" "complete"
    info "Completed setting recommended systemd database values"
fi

nic_count="$(curl -sf --retry 20 -H "Metadata-Flavor: Google" "http://169.254.169.254/computeMetadata/v1/instance/network-interfaces/?recursive=true" | jq --raw-output '.|length')"
nic_count="${nic_count:-1}"
if [ "${nic_count}" -gt 1 ] && [ ! -f /config/cloud/.mgmtInterface ]; then
    info "Getting management interface configuration from metadata"
    target_address="$(curl -sf --retry 20 -H "Metadata-Flavor: Google" "http://169.254.169.254/computeMetadata/v1/instance/network-interfaces/${MGMT_INTERFACE}/ip")"
    target_netmask="$(curl -sf --retry 20 -H "Metadata-Flavor: Google" "http://169.254.169.254/computeMetadata/v1/instance/network-interfaces/${MGMT_INTERFACE}/subnetmask")"
    target_gateway="$(curl -sf --retry 20 -H "Metadata-Flavor: Google" "http://169.254.169.254/computeMetadata/v1/instance/network-interfaces/${MGMT_INTERFACE}/gateway")"
    target_mtu="$(curl -sf --retry 20 -H "Metadata-Flavor: Google" "http://169.254.169.254/computeMetadata/v1/instance/network-interfaces/${MGMT_INTERFACE}/mtu")"
    target_network="$(ipcalc -n "${target_address}" "${target_netmask}" | cut -d= -f2)"
    # NOTE: this configuration is based on f5devcentral/terraform-gcp bigip-module boarding script, unless called out
    info "Resetting management interface"
    set_status_attribute "mgmt-iface" "in-progress"
    tmsh modify sys global-settings gui-setup disabled
    tmsh modify sys global-settings mgmt-dhcp disabled
    tmsh delete sys management-route all
    tmsh delete sys management-ip all
    info "Configuring management interface"
    tmsh create sys management-ip "${target_address}/32"
    info "  management-ip is set to '${target_address}/32'"
    tmsh create sys management-route mgmt_gw network "${target_gateway}/32" type interface mtu "${target_mtu}"
    info "  management-route mgmt_gw is set to 'network ${target_gateway}/32 type interface mtu ${target_mtu}'"
    tmsh create sys management-route mgmt_net network "${target_network}/${target_netmask}" gateway "${target_gateway}" mtu "${target_mtu}"
    info "  management-route mgmt_net is set to 'network ${target_network}/${target_netmask} gateway ${target_gateway} mtu ${target_mtu}'"
    tmsh create sys management-route default gateway "${target_gateway}" mtu "${target_mtu}"
    info "  management-route default is set to 'gateway ${target_gateway} mtu ${target_mtu}'"
    tmsh modify sys global-settings remote-host add { metadata.google.internal { hostname metadata.google.internal addr 169.254.169.254 } }
    tmsh modify sys management-dhcp sys-mgmt-dhcp-config request-options delete { ntp-servers }
    # MEmes - make sure the GCP metadata server is used for DNS and NTP, at least until user explicitly overrides in Declarative Onboarding
    tmsh modify sys dns name-servers add { 169.254.169.254 }
    tmsh modify sys ntp servers add { 169.254.169.254 }
    tmsh save /sys config
    touch /config/cloud/.mgmtInterface
    info "Setup of management interface is complete."
fi

# Is a management NIC swap necessary?
current_mgmt_nic="$(tmsh list sys db provision.managementeth value 2>/dev/null | awk -F\" 'NR==2 {print $2}')"
if [ "${nic_count}" -gt 1 ] && [ "${current_mgmt_nic}" != "eth${MGMT_INTERFACE}" ]; then
    info "Management NIC swap is necessary; updating database"
    bigstart stop tmm
    tmsh modify sys db provision.managementeth value "eth${MGMT_INTERFACE}"
    info " provision.managementeth set to 'eth${MGMT_INTERFACE}'"
    tmsh modify sys db provision.1nicautoconfig value disable
    info " provision.1nicautoconfig set to 'disable'"
    tmsh save /sys config
    [ -e "/etc/ts/common/image.cfg" ] && \
        sed -i "s/iface=eth[0-7]/iface=eth${MGMT_INTERFACE}/g" /etc/ts/common/image.cfg
    info "Rebooting for management NIC swap."
    reboot
    exit 0
else
    info "Management NIC swap is not needed; continuing"
fi

# When the management interface is reset access to external IPs is temporarily broken; update the guest-status attribute
# after any reboot has happened.
if [ "${nic_count}" -gt 1 ] && [ -f /config/cloud/.mgmtInterface ]; then
    set_status_attribute "mgmt-iface" "complete"
fi

if [ -x /usr/local/bin/f5-bigip-runtime-init ]; then
    info "Runtime-init package already installed"
    set_status_attribute "runtime-init-install" "complete"
else
    if [ -z "${RUNTIME_INIT_URL}" ] || [ "${RUNTIME_INIT_URL}" = "SKIP" ]; then
        set_status_attribute "runtime-init-download" "skipped"
        info "Skipping runtime-init package download, as requested"
    else
        # Download and execute runtime-init
        info "Downloading runtime-init installer from ${RUNTIME_INIT_URL}"
        set_status_attribute "runtime-init-download" "in-progress"
        download "${RUNTIME_INIT_URL}" "/var/config/rest/downloads/f5-bigip-runtime-init.gz.run" || \
            error "Failed to download ${RUNTIME_INIT_URL}: exit code: $?"
        set_status_attribute "runtime-init-download" "complete"
        if [ -z "${RUNTIME_INIT_SHA256SUM}" ] || [ "${RUNTIME_INIT_SHA256SUM}" = "SKIP" ]; then
            set_status_attribute "runtime-init-checksum" "skipped"
            info "Skipping runtime-init package checksum validation, as requested"
        else
            if [ -f /var/config/rest/downloads/f5-bigip-runtime-init.gz.run ]; then
                set_status_attribute "runtime-init-checksum" "in-progress"
                echo "${RUNTIME_INIT_SHA256SUM} /var/config/rest/downloads/f5-bigip-runtime-init.gz.run" | \
                    sha256sum --status --check || \
                        error "Failed to verify integrity of download from ${RUNTIME_INIT_URL}: exit code: $?"
                set_status_attribute "runtime-init-checksum" "complete"
            fi
        fi
    fi
    if [ ! -f /var/config/rest/downloads/f5-bigip-runtime-init.gz.run ]; then
        info "Cannot install runtime-init package as bundle is missing"
        set_status_attribute "runtime-init-install" "missing-bundle"
    else
        info "Installing runtime-init package"
        set_status_attribute "runtime-init-install" "in-progress"
        # shellcheck disable=SC2086
        bash /var/config/rest/downloads/f5-bigip-runtime-init.gz.run -- ${RUNTIME_INIT_INSTALLER_EXTRA_ARGS} --cloud gcp || \
            error "Failed to install runtime-init: exit code $?"
        set_status_attribute "runtime-init-install" "complete"
    fi
fi
if [ -x /usr/local/bin/f5-bigip-runtime-init ]; then
    info "Executing runtime-init"
    set_status_attribute "runtime-init-execution" "in-progress"
    # Apply all runtime-init-conf JSON or YAML files in /config/cloud in sorted order to allow stacking.
    find /config/cloud -maxdepth 1 -type f -iregex '.*_runtime-init-conf\.\(json\|yaml\)$' | sort --ignore-case | \
        while read -r config_file; do
            if [ -f "${config_file}" ]; then
                attempt=0
                while [ "${attempt}" -lt 3 ]; do
                    # shellcheck disable=SC2086
                    /usr/local/bin/f5-bigip-runtime-init ${RUNTIME_INIT_EXTRA_ARGS} --config-file "${config_file}"
                    retval=$?
                    [ "${retval}" -eq 0 ] && break
                    info "${attempt}: Failed to execute runtime-init for ${config_file}: exit code: ${retval}; sleeping before retrying"
                    sleep 10
                    attempt=$((attempt+1))
                done
                [ "${attempt}" -ge 3 ] && \
                    error "Failed to execute runtime-init for ${config_file} after ${attempt} tries: exit code: ${retval}"
                info "Runtime-init configuration ${config_file} has been applied; moving file to ${config_file}.executed"
                mv "${config_file}" "${config_file}.executed" || \
                    error "Failed to move runtime-init configuration file ${config_file} to ${config_file}.executed; exit code $?"
            else
                info "Runtime-init configuration file ${config_file} was not found; skipping"
            fi
        done
    set_status_attribute "runtime-init-execution" "complete"
fi

set_status_attribute "onboarding" "complete"
info "Onboarding complete"
