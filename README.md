# BIG-IP HA on Google Cloud

This Terraform module will create two BIG-IP instances that will have the required
infrastructure for high-availability using Device Groups and Failover Sync.

## Details

<!-- markdownlint-disable no-inline-html no-bare-urls -->
<!-- BEGINNING OF PRE-COMMIT-TERRAFORM DOCS HOOK -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 0.14.5 |
| <a name="requirement_google"></a> [google](#requirement\_google) | >= 3.85.0 |

## Modules

| Name | Source | Version |
|------|--------|---------|
| <a name="module_instances"></a> [instances](#module\_instances) | F5Networks/bigip-module/gcp | 1.1.0 |

## Resources

| Name | Type |
|------|------|
| [google_compute_firewall.data_sync](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_firewall) | resource |
| [google_compute_firewall.mgt_sync](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_firewall) | resource |
| [google_compute_instance_group.group](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_instance_group) | resource |
| [google_compute_target_instance.target](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_target_instance) | resource |
| [google_compute_subnetwork.dsc_data](https://registry.terraform.io/providers/hashicorp/google/latest/docs/data-sources/compute_subnetwork) | data source |
| [google_compute_subnetwork.dsc_mgmt](https://registry.terraform.io/providers/hashicorp/google/latest/docs/data-sources/compute_subnetwork) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_prefix"></a> [prefix](#input\_prefix) | The prefix to use when naming resources managed by this module. Must be RFC1035<br>compliant and between 1 and 58 characters in length, inclusive. | `string` | n/a | yes |
| <a name="input_project_id"></a> [project\_id](#input\_project\_id) | The GCP project identifier where the BIG-IP HA pair will be created | `string` | n/a | yes |
| <a name="input_service_account"></a> [service\_account](#input\_service\_account) | The email address of the service account which will be used for BIG-IP instances. | `string` | n/a | yes |
| <a name="input_zones"></a> [zones](#input\_zones) | The compute zones where where the BIG-IP instances will be deployed. At least one<br>zone must be provided; if more than one zone is given, the instances will be<br>distributed among them. | `list(string)` | n/a | yes |
| <a name="input_AS3_URL"></a> [AS3\_URL](#input\_AS3\_URL) | URL to download the BIG-IP Application Service Extension 3 (AS3) module | `string` | `"https://github.com/F5Networks/f5-appsvcs-extension/releases/download/v3.28.0/f5-appsvcs-3.28.0-3.noarch.rpm"` | no |
| <a name="input_CFE_URL"></a> [CFE\_URL](#input\_CFE\_URL) | URL to download the BIG-IP Cloud Failover Extension module | `string` | `"https://github.com/F5Networks/f5-cloud-failover-extension/releases/download/v1.8.0/f5-cloud-failover-1.8.0-0.noarch.rpm"` | no |
| <a name="input_DO_URL"></a> [DO\_URL](#input\_DO\_URL) | URL to download the BIG-IP Declarative Onboarding module | `string` | `"https://github.com/F5Networks/f5-declarative-onboarding/releases/download/v1.21.0/f5-declarative-onboarding-1.21.0-3.noarch.rpm"` | no |
| <a name="input_FAST_URL"></a> [FAST\_URL](#input\_FAST\_URL) | URL to download the BIG-IP FAST module | `string` | `"https://github.com/F5Networks/f5-appsvcs-templates/releases/download/v1.9.0/f5-appsvcs-templates-1.9.0-1.noarch.rpm"` | no |
| <a name="input_INIT_URL"></a> [INIT\_URL](#input\_INIT\_URL) | URL to download the BIG-IP runtime init | `string` | `"https://cdn.f5.com/product/cloudsolutions/f5-bigip-runtime-init/v1.2.1/dist/f5-bigip-runtime-init-1.2.1-1.gz.run"` | no |
| <a name="input_TS_URL"></a> [TS\_URL](#input\_TS\_URL) | URL to download the BIG-IP Telemetry Streaming module | `string` | `"https://github.com/F5Networks/f5-telemetry-streaming/releases/download/v1.20.0/f5-telemetry-1.20.0-3.noarch.rpm"` | no |
| <a name="input_automatic_restart"></a> [automatic\_restart](#input\_automatic\_restart) | Determines if the BIG-IP VMs should be automatically restarted if terminated by<br>GCE. Defaults to true to match expected GCE behaviour. | `bool` | `true` | no |
| <a name="input_custom_user_data"></a> [custom\_user\_data](#input\_custom\_user\_data) | Override the onboarding BASH script used by F5Networks/terraform-gcp-bigip-module. | `string` | `null` | no |
| <a name="input_disk_size_gb"></a> [disk\_size\_gb](#input\_disk\_size\_gb) | Use this flag to set the boot volume size in GB. If left at the default value<br>the boot disk will have the same size as the base image. | `number` | `null` | no |
| <a name="input_disk_type"></a> [disk\_type](#input\_disk\_type) | The boot disk type to use with instances; can be 'pd-balanced', 'pd-ssd' (default),<br>or 'pd-standard'. | `string` | `"pd-ssd"` | no |
| <a name="input_external_subnet_ids"></a> [external\_subnet\_ids](#input\_external\_subnet\_ids) | TODO @memes - update | <pre>list(list(object({<br>    subnet_id            = string<br>    public_ip            = bool<br>    private_ip_primary   = string<br>    private_ip_secondary = string<br>  })))</pre> | <pre>[<br>  [<br>    {<br>      "private_ip_primary": null,<br>      "private_ip_secondary": null,<br>      "public_ip": null,<br>      "subnet_id": null<br>    }<br>  ],<br>  [<br>    {<br>      "private_ip_primary": null,<br>      "private_ip_secondary": null,<br>      "public_ip": null,<br>      "subnet_id": null<br>    }<br>  ]<br>]</pre> | no |
| <a name="input_f5_password"></a> [f5\_password](#input\_f5\_password) | The admin password of the F5 Bigip that will be deployed | `string` | `""` | no |
| <a name="input_f5_ssh_publickey"></a> [f5\_ssh\_publickey](#input\_f5\_ssh\_publickey) | The path to the SSH public key to install on BIG-IP instances for admin access. | `string` | `"~/.ssh/id_rsa.pub"` | no |
| <a name="input_f5_username"></a> [f5\_username](#input\_f5\_username) | The admin username of the F5 Bigip that will be deployed | `string` | `"bigipuser"` | no |
| <a name="input_gcp_secret_manager_authentication"></a> [gcp\_secret\_manager\_authentication](#input\_gcp\_secret\_manager\_authentication) | Whether to use secret manager to pass authentication | `bool` | `false` | no |
| <a name="input_gcp_secret_name"></a> [gcp\_secret\_name](#input\_gcp\_secret\_name) | The secret to get the secret version for | `string` | `""` | no |
| <a name="input_gcp_secret_version"></a> [gcp\_secret\_version](#input\_gcp\_secret\_version) | (Optional)The version of the secret to get. If it is not provided, the latest version is retrieved. | `string` | `"latest"` | no |
| <a name="input_image"></a> [image](#input\_image) | The self-link URI for a BIG-IP image to use as a base for the VM cluster. This<br>can be an official F5 image from GCP Marketplace, or a customised image. | `string` | `"projects/f5-7626-networks-public/global/images/f5-bigip-16-1-1-0-0-16-payg-good-1gbps-210917181041"` | no |
| <a name="input_internal_subnet_ids"></a> [internal\_subnet\_ids](#input\_internal\_subnet\_ids) | TODO @memes - update | <pre>list(list(object({<br>    subnet_id          = string<br>    public_ip          = bool<br>    private_ip_primary = string<br>  })))</pre> | <pre>[<br>  [<br>    {<br>      "private_ip_primary": null,<br>      "public_ip": null,<br>      "subnet_id": null<br>    }<br>  ],<br>  [<br>    {<br>      "private_ip_primary": null,<br>      "public_ip": null,<br>      "subnet_id": null<br>    }<br>  ]<br>]</pre> | no |
| <a name="input_labels"></a> [labels](#input\_labels) | An optional map of string key:value pairs that will be applied to all resources<br>created that accept labels. Default is an empty map. | `map(string)` | `{}` | no |
| <a name="input_libs_dir"></a> [libs\_dir](#input\_libs\_dir) | Directory on the BIG-IP to download the A&O Toolchain into | `string` | `"/config/cloud/gcp/node_modules"` | no |
| <a name="input_machine_type"></a> [machine\_type](#input\_machine\_type) | The machine type to use for BIG-IP VMs; this may be a standard GCE machine type,<br>or a customised VM ('custom-VCPUS-MEM\_IN\_MB'). Default value is 'n1-standard-4'.<br>*Note:* machine\_type is highly-correlated with network bandwidth and performance;<br>an N2 machine type will give better performance but has limited regional availability. | `string` | `"n1-standard-4"` | no |
| <a name="input_metadata"></a> [metadata](#input\_metadata) | Provide custom metadata values for BIG-IP instance | `map(string)` | `{}` | no |
| <a name="input_mgmt_subnet_ids"></a> [mgmt\_subnet\_ids](#input\_mgmt\_subnet\_ids) | TODO @memes - update<br>List of maps of subnetids of the virtual network where the virtual machines will reside. | <pre>list(list(object({<br>    subnet_id          = string<br>    public_ip          = bool<br>    private_ip_primary = string<br>  })))</pre> | <pre>[<br>  [<br>    {<br>      "private_ip_primary": null,<br>      "public_ip": null,<br>      "subnet_id": null<br>    }<br>  ],<br>  [<br>    {<br>      "private_ip_primary": null,<br>      "public_ip": null,<br>      "subnet_id": null<br>    }<br>  ]<br>]</pre> | no |
| <a name="input_min_cpu_platform"></a> [min\_cpu\_platform](#input\_min\_cpu\_platform) | An optional constraint used when scheduling the BIG-IP VMs; this value prevents<br>the VMs from being scheduled on hardware that doesn't meet the minimum CPU<br>micro-architecture. Default value is 'Intel Skylake'. | `string` | `"Intel Skylake"` | no |
| <a name="input_onboard_log"></a> [onboard\_log](#input\_onboard\_log) | Directory on the BIG-IP to store the cloud-init logs | `string` | `"/var/log/startup-script.log"` | no |
| <a name="input_preemptible"></a> [preemptible](#input\_preemptible) | If set to true, the BIG-IP instances will be deployed on preemptible VMs, which<br>could be terminated at any time, and have a maximum lifetime of 24 hours. Default<br>value is false. DO NOT SET TO TRUE UNLESS YOU UNDERSTAND THE RAMIFICATIONS! | `string` | `false` | no |
| <a name="input_sleep_time"></a> [sleep\_time](#input\_sleep\_time) | The number of seconds/minutes of delay to build into creation of BIG-IP VMs; default is 250. BIG-IP requires a few minutes to complete the onboarding process and this value can be used to delay the processing of dependent Terraform resources. | `string` | `"300s"` | no |
| <a name="input_targets"></a> [targets](#input\_targets) | Defines the target types to create for integration with GCP forwarding-rules, and/or<br>load balancers. | <pre>object({<br>    groups    = bool<br>    instances = bool<br>  })</pre> | <pre>{<br>  "groups": true,<br>  "instances": false<br>}</pre> | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_mgmtPublicIPs"></a> [mgmtPublicIPs](#output\_mgmtPublicIPs) | A map of BIG-IP instance name to public IP address, if any, on the management interface. |
| <a name="output_names"></a> [names](#output\_names) | The instance names of the BIG-IPs. |
| <a name="output_self_links"></a> [self\_links](#output\_self\_links) | A map of BIG-IP instance name to fully-qualified self-links. |
| <a name="output_target_groups"></a> [target\_groups](#output\_target\_groups) | A list of fully-qualified BIG-IP unmanaged instance group self-links. |
| <a name="output_target_instances"></a> [target\_instances](#output\_target\_instances) | A list of fully-qualified target instance self-links for the BIG-IPs. |
<!-- END OF PRE-COMMIT-TERRAFORM DOCS HOOK -->
<!-- markdownlint-enable no-inline-html no-bare-urls -->
