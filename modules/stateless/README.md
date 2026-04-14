# Stateless BIG-IP Active-Active HA on Google Cloud

> NOTE: This module is pre-release and functionality can change abruptly prior to v1.0 release. Be sure to pin to an
> exact version to avoid unintentional breakage due to updates.

This Terraform module creates Google Cloud infrastructure for an *opinionated, stateless, regional or zonal cluster* of
F5 BIG-IP VE instances, where Google Cloud determines when instances are created, destroyed and how they are named. You
must provide a full declarative onboarding payload appropriate to your scenario that can be applied identically to all
instances.

![BIG-IP VE and supporting resources created by module](./deployment.png)
*Figure 1: The Google Cloud resources created by the module.*

> For the purpose of this module, *stateless* is taken to mean that each BIG-IP VE instance is independent of every other
> instance in the cluster, providing an Active-Active (all instances could handle traffic) HA deployment.
>
> The root module is [stateful](../../) and can be used to create an Active-Standby or Active-Active HA cluster of BIG-IP
> VE instances that share configuration through sync groups.

## What makes the module opinionated, and why might it be wrong for me?

F5's published [BIG-IP on Google Cloud Terraform module][upstream] can be used to create a set of VE instances that can
be joined into a device sync group when combined with additional effort/configuration, but it has no support for
*stateless* clusters of BIG-IP VE instances.

1. Virtual machine lifecycle

   > OPINION: Google Cloud will be responsible for launching and terminating BIG-IP VE instances as needed.

   The module provides a `num_instances` input to set the size of the cluster; module consumers can change that value and
   reapply to have Google Cloud automatically add or terminate instances as needed for manual scaling.

   Autoscaling can be supported by setting `num_instances` to 0, and adding the instance group to an autoscaler; see
   [autoscaling](../../examples/autoscaling-nlb/) for an example.

   > NOTE: Per-instance naming or lifecycle management is not supported for *stateless* clusters.

2. Subnetwork and IP addressing

   > OPINION: Subnetworks used and addressing flags should be consistent on all created instances, and the cluster should
   > be *regional* or *zonal*.

   For these reasons this module exposes the input `interfaces` to define the subnetwork self-links, and public IP
   assignment flag to use for each entry in the list. These are applied to the VM in the order provided; e.g. the first
   `interfaces` entry will define the network attachment for `eth0`, the second for `eth1`, etc., through `eth7` if
   applicable. By default, the onboarding scripts will expect `eth1` to become the management (or control-plane)
   interface, so that the VM can accept traffic from a Google Cloud external load balancer. This behavior can be changed
   using the `management_interface_index` variable.

   > NOTE: Per-instance IP addressing is not supported for *stateless* clusters.

3. Module responsibility for onboarding stops at runtime-init

   > OPINION: Consumers of the module must provide a runtime-init configuration to set passwords, enable data-plane, and
   > add applications, etc.

   There are simply too many configuration options and deployment scenarios to have a one-size-fits-all module suitable
   for every situation. This module will provide a cloud-init file through `user-data` metadata value that will configure
   the management interface (nic1) of every instance from Compute Engine metadata, attempt to download and install
   runtime-init, then execute a provided configuration file.

   If a runtime-init configuration file is not provided the instances will not be fully configured; the admin user
   password will be unknown, traffic will not be processed, and the instance group manager will kill instances.

<!-- markdownlint-disable no-inline-html no-bare-urls table-column-style -->
<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.5 |
| <a name="requirement_google"></a> [google](#requirement\_google) | >= 7.1 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [google_compute_firewall.livez](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_firewall) | resource |
| [google_compute_health_check.livez](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_health_check) | resource |
| [google_compute_region_instance_group_manager.mig](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_region_instance_group_manager) | resource |
| [google_compute_instance_template.template](https://registry.terraform.io/providers/hashicorp/google/latest/docs/data-sources/compute_instance_template) | data source |
| [google_compute_subnetwork.external](https://registry.terraform.io/providers/hashicorp/google/latest/docs/data-sources/compute_subnetwork) | data source |
| [google_compute_zones.zones](https://registry.terraform.io/providers/hashicorp/google/latest/docs/data-sources/compute_zones) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_instance_template"></a> [instance\_template](#input\_instance\_template) | The Compute Engine Instance Template self-link or qualified identifier that contains the common instance parameters to<br/>apply to all instances launched by this module.<br/>NOTE: If the module variables `labels`, and `metadata` are not empty they will be merged with the equivalent values<br/>contained in the Instance Template. | `string` | n/a | yes |
| <a name="input_prefix"></a> [prefix](#input\_prefix) | The prefix to use when naming resources managed by this module. Must be RFC1035 compliant and between 1 and 37<br/>characters in length, inclusive. | `string` | n/a | yes |
| <a name="input_project_id"></a> [project\_id](#input\_project\_id) | The GCP project identifier where the BIG-IP instances will be created. | `string` | n/a | yes |
| <a name="input_description"></a> [description](#input\_description) | An optional description to add to the Regional Managed Instance Group created for stateless BIG-IP HA. | `string` | `"Managed group of regional stateless BIG-IP instances"` | no |
| <a name="input_health_check"></a> [health\_check](#input\_health\_check) | Provide an optional existing Google Cloud health check to use for instance health check (e.g. is the BIG-IP "alive"),<br/>and an optional TCP port that a health check will use. If the self-link value is null/empty (default) a simple HTTP<br/>health check will be created that attempts to connect to "/" on the TCP port specified. The default value for TCP port<br/>is 26000, and the default initial delay is 600s.<br/>NOTE: In most cases a GCP Firewall Rule is required to allow health check probes to reach the BIG-IP instances; this<br/>module will create a suitable rule unless port is explicitly set to null. | <pre>object({<br/>    self_link         = optional(string)<br/>    port              = optional(number, 26000)<br/>    initial_delay_sec = optional(number, 600)<br/>  })</pre> | <pre>{<br/>  "initial_delay_sec": 600,<br/>  "port": 26000,<br/>  "self_link": null<br/>}</pre> | no |
| <a name="input_labels"></a> [labels](#input\_labels) | An optional map of string key:value pairs that will be applied to all resources created that accept labels, overriding<br/>  the value present in the Instance Template. Default is null. | `map(string)` | `null` | no |
| <a name="input_metadata"></a> [metadata](#input\_metadata) | An optional set of metadata values to add to all BIG-IP instances.<br/>NOTE: Setting this value will override the settings in the instance template, including the scripts to onboard the<br/>BIG-IPs. | `map(string)` | `null` | no |
| <a name="input_named_ports"></a> [named\_ports](#input\_named\_ports) | An optional map of names to port number that will become a set of named ports in the instance group. | `map(number)` | `null` | no |
| <a name="input_num_instances"></a> [num\_instances](#input\_num\_instances) | The number of BIG-IP instances to create as a stateless group; if using with an autoscaler this value should be set to<br/>0. Default value is 2. | `number` | `2` | no |
| <a name="input_zones"></a> [zones](#input\_zones) | An optional list of Compute Engine Zone names where where the BIG-IP instances will be deployed; if null or empty<br/>(default) BIG-IP instances will be randomly distributed to known zones in the subnetwork region. If one or more zone<br/>is given, the instances will be constrained to the zones specified. | `list(string)` | `null` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_instance_group"></a> [instance\_group](#output\_instance\_group) | The Compute Engine instance group self-link of the stateless BIG-IP VMs. |
| <a name="output_instance_group_manager"></a> [instance\_group\_manager](#output\_instance\_group\_manager) | The Compute Engine instance group manager self-link of the stateless BIG-IP VMs. |
<!-- END_TF_DOCS -->
<!-- markdownlint-enable no-inline-html no-bare-urls table-column-style -->

[upstream]: https://registry.terraform.io/modules/F5Networks/bigip-module/gcp/latest
