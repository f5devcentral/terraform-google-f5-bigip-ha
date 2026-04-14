# Troubleshooting BIG-IP VE in Google Cloud

The [onboarding shell script](./modules/template/files/onboard.sh) performs these steps:

1. Apply recommended system database values - one time operation
1. Configure management interface, and reboot to enforce network interface assignment - one time operation
   > This is only when the number of network interfaces attached to the VE is >1
1. Download the F5 BIG-IP runtime-init package from F5 CDN (or other location if overridden)
1. Install the F5 BIG-IP runtime-init package
1. For every matching runtime-init configuration file, execute F5 BIG-IP runtime-init

Where possible, the script will retry operations a few times to get past transient issues. This means it can take up to
10 minutes before the BIG-IP has reached fully onboarded state.

## Guest attributes

If the BIG-IP VEs were provisioned with the metadata key `enable-guest-attributes` set to `TRUE`, the onboarding script
will report status as [guest attributes] in the `f5-big-ip` namespace, providing an indication of how onboarding is
progressing. The key `onboarding` can be used to gauge overall progress as it will change from the value `in-progress`
to `complete` when the onboarding script succeeds.

For example, a BIG-IP with 2 or more NICs which has successfully completed all the onboarding steps will have an output
similar to this:

```shell
gcloud compute instances get-guest-attributes bigip-01 \
    --zone us-west1-c \
    --project my-project-id
```

```text
NAMESPACE  KEY                     VALUE
f5-big-ip  mgmt-iface              complete
f5-big-ip  onboarding              complete
f5-big-ip  runtime-init-checksum   complete
f5-big-ip  runtime-init-download   complete
f5-big-ip  runtime-init-execution  complete
f5-big-ip  runtime-init-install    complete
f5-big-ip  set-db                  complete
```

> NOTE: BIG-IP VEs provisioned with a single NIC will be missing the `mgmt-iface` attribute, since that phase is not
> applicable.

## Serial console

The onboarding script sends INFO and ERROR messages to systemd journal and to virtual serial port 0. These entries can
be viewed in the Google Cloud console, or retrieved using `gcloud` commands.

```shell
gcloud compute instances get-serial-port-output bigip-01 \
    --zone us-west1-c \
    --project my-project-id
```

> NOTE: Change `get-serial-port-output` to `tail-serial-port-output` to see real-time updates as they are echoed to the
> serial port.

Near the end of onboarding the output should look similar to this:

<!-- markdownlint-disable -->
```text
[  362.153391] onboard.sh[4407]: 2026-04-14T15:36:27.337Z [11621]: info: Executing custom post_onboard_enabled commands
[  362.156579] onboard.sh[4407]: 2026-04-14T15:36:27.338Z [11621]: info: Executing inline shell command: tmsh save sys config
[  368.924056] onboard.sh[4407]: 2026-04-14T15:36:34.105Z [11621]: info: Shell command: tmsh save sys config execution completed; response: Saving running configuration...
[  368.924632] onboard.sh[4407]: /config/bigip.conf
[  368.924991] onboard.sh[4407]: /config/bigip_base.conf
[  368.925298] onboard.sh[4407]: /config/bigip_script.conf
[  368.925599] onboard.sh[4407]: /config/bigip_user.conf
[  368.925899] onboard.sh[4407]: /config/partitions/Applications/bigip.conf
[  368.926209] onboard.sh[4407]: Saving Ethernet map ...done
[  368.926501] onboard.sh[4407]: Saving PCI map ...
[  368.926793] onboard.sh[4407]: - verifying checksum .../var/run/f5pcimap: OK
[  368.927080] onboard.sh[4407]: done
[  368.927416] onboard.sh[4407]: - saving ...done
[  368.927724] onboard.sh[4407]: 2026-04-14T15:36:34.108Z [11621]: info: All operations finished successfully
[  398.961548] onboard.sh[4407]: /config/cloud/onboard.sh: INFO: Runtime-init configuration /config/cloud/00_runtime-init-conf.yaml has been applied; moving file to /config/cloud/00_runtime-init-conf.yaml.executed
[  399.000932] onboard.sh[4407]: /config/cloud/onboard.sh: INFO: set_status_attribute: 0: Successfully updated guest-attribute 'f5-bigip-ip/runtime-init-execution' with value 'complete'
[  399.025810] onboard.sh[4407]: /config/cloud/onboard.sh: INFO: set_status_attribute: 0: Successfully updated guest-attribute 'f5-bigip-ip/onboarding' with value 'complete'
[  399.026460] onboard.sh[4407]: /config/cloud/onboard.sh: INFO: Onboarding complete
[  399.060787] systemctl[23099]: Created symlink from /etc/systemd/system/multi-user.target.wants/f5-gce-reset-management-route.service to /etc/systemd/system/f5-gce-reset-management-route.service.
[  399.229197] systemctl[23117]: Removed symlink /etc/systemd/system/multi-user.target.wants/f5-gce-onboard.service.
[  OK  ] Reached target Multi-User System.
```
<!-- markdownlint-enable -->

* Entries from the onboarding script will contain a duration since boot, the string `onboard.sh` and the process id.
* Errors will contain the string `ERROR:`

[guest attributes]: https://docs.cloud.google.com/compute/docs/metadata/manage-guest-attributes
