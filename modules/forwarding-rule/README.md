# Forwarding Rule

This helper module will create a [Forwarding Rule](https://cloud.google.com/load-balancing/docs/forwarding-rule-concepts)
that will direct TCP and/or UDP traffic to a single VM, and is typically used
for BIG-IP VMs that are utilizing CFE to manage GCP API objects on failover.

## Example: TCP and UDP external rule

```hcl
module "tcp_udp_nlb" {
  source                 = "github.com/f5devcentral/terraform-google-f5-bigip-ha//modules/forwarding-rule"
  project_id             = var.project_id
  region                 = var.region
  subnet                 = var.external_subnet
  prefix                 = "ext-tcp-udp"
  instance_groups        = module.bigip-cluster.target_instances
  address                = var.reserved_external_address
}
```

## Example: TCP-only load balancing

```hcl
module "tcp_nlb" {
  source                 = "github.com/f5devcentral/terraform-google-f5-bigip-ha//modules/forwarding-rule"
  project_id             = var.project_id
  region                 = var.region
  subnet                 = var.external_subnet
  prefix                 = "ext-tcp"
  instance_groups        = module.bigip-cluster.target_instances
  address                = var.reserved_external_address
  protocols              = [
    "TCP",
  ]
}
```

## Example: TCP, UDP, ESP, and ICMP load balancing

```hcl
module "l3_default_nlb" {
  source                 = "github.com/f5devcentral/terraform-google-f5-bigip-ha//modules/forwarding-rule"
  project_id             = var.project_id
  region                 = var.region
  subnet                 = var.external_subnet
  prefix                 = "ext-l3"
  instance_groups        = module.bigip-cluster.target_instances
  address                = var.reserved_external_address
  protocols              = [
    "L3_DEFAULT",
  ]
}
```

<!-- markdownlint-disable no-inline-html no-bare-urls -->
<!-- BEGINNING OF PRE-COMMIT-TERRAFORM DOCS HOOK -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 0.14.5 |
| <a name="requirement_google"></a> [google](#requirement\_google) | >= 3.85 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [google_compute_forwarding_rule.fwd](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_forwarding_rule) | resource |
| [google_compute_subnetwork.subnet](https://registry.terraform.io/providers/hashicorp/google/latest/docs/data-sources/compute_subnetwork) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_prefix"></a> [prefix](#input\_prefix) | The prefix to use when naming resources managed by this module. Must be RFC1035<br>compliant and between 1 and 52 characters in length, inclusive. | `string` | n/a | yes |
| <a name="input_project_id"></a> [project\_id](#input\_project\_id) | The GCP project identifier where the BIG-IP cluster will be created | `string` | n/a | yes |
| <a name="input_region"></a> [region](#input\_region) | The compute region where where the forwarding-rules will be deployed. | `string` | n/a | yes |
| <a name="input_targets"></a> [targets](#input\_targets) | The VM target instance self-links for the forwarding-rule(s). | `set(string)` | n/a | yes |
| <a name="input_address"></a> [address](#input\_address) | The IPv4 address to use with the forwarding rule. | `string` | `null` | no |
| <a name="input_is_external"></a> [is\_external](#input\_is\_external) | A boolean flag to determine if the forwarding-rule will be for ingress from external<br>internet (default), or it it will be forwarding internal only traffic. | `bool` | `true` | no |
| <a name="input_labels"></a> [labels](#input\_labels) | An optional map of string key:value pairs to assign to created resources. | `map(string)` | `{}` | no |
| <a name="input_protocols"></a> [protocols](#input\_protocols) | The IP protocols that will be enabled in the forwarding rule(s); a rule will be<br>created for each protocol specified. NOTE: L3\_DEFAULT is only valid for an external<br>forwarding-rule instance (i.e. when is\_external = true).<br><br>Default value is ["TCP", "UDP"]. | `set(string)` | <pre>[<br>  "TCP",<br>  "UDP"<br>]</pre> | no |
| <a name="input_subnet"></a> [subnet](#input\_subnet) | The fully-qualified subnetwork self-link to which the forwarding rule will be<br>attached. Required if `is_external` is false; Terraform apply will fail if<br>subnet is null/empty and an internal forwarding rule is requested. | `string` | `null` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_addresses"></a> [addresses](#output\_addresses) | A list of unique forwarding-rule IPv4 and/or IPv6 addresses. |
| <a name="output_names"></a> [names](#output\_names) | A list of forwarding-rule names. |
| <a name="output_protocol_addresses"></a> [protocol\_addresses](#output\_protocol\_addresses) | A map of protocols to forwarding-rule IPv4 and/or IPv6 address. |
| <a name="output_self_links"></a> [self\_links](#output\_self\_links) | A map of  protocols to fully-qualified forwarding-rule self-links. |
<!-- END OF PRE-COMMIT-TERRAFORM DOCS HOOK -->
<!-- markdownlint-enable no-inline-html no-bare-urls -->
