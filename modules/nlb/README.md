# Network load balancer

This helper module will create an [Network TCP/UDP load balancer](https://cloud.google.com/load-balancing/docs/network)
that will direct TCP and/or UDP traffic to the VMs in a set of instance groups.
NLBs are not network-aware; all traffic will be directed to NIC0 of the VMs that
constitute the instance groups.

> NOTE: NLBs support [ESP and ICMP protocols](https://cloud.google.com/load-balancing/docs/network/networklb-backend-service#forwarding-rule-protocols)
> in [Preview](https://cloud.google.com/products#product-launch-stages). This is
> permitted by the module if you set the `protocols` list to have a single
> "L3_DEFAULT" entry, which effectively permits TCP, UDP, ESP and ICMP traffic to
> ingress through the NLB. As per GCP, preview options are generally unsupported
> and do not provide any SLAs or support commitments.

## Example: TCP and UDP load balancing

```hcl
module "tcp_udp_nlb" {
  source                 = "github.com/f5devcentral/terraform-gcp-f5-sca//modules/cluster/nlb"
  project_id             = var.project_id
  region                 = var.region
  subnet                 = var.external_subnet
  prefix                 = "ext-tcp-udp"
  instance_groups        = module.bigip-cluster.instance_groups
  target_service_account = var.bigip-sa
  address                = var.reserved_external_nlb_address
}
```

## Example: TCP-only load balancing

```hcl
module "tcp_nlb" {
  source                 = "github.com/f5devcentral/terraform-gcp-f5-sca//modules/cluster/nlb"
  project_id             = var.project_id
  region                 = var.region
  subnet                 = var.external_subnet
  prefix                 = "ext-tcp"
  instance_groups        = module.bigip-cluster.instance_groups
  target_service_account = var.bigip-sa
  address                = var.reserved_external_nlb_address
  protocols              = [
    "TCP",
  ]
}
```

## Example: TCP, UDP, ESP, and ICMP load balancing

```hcl
module "l3_default_nlb" {
  source                 = "github.com/f5devcentral/terraform-gcp-f5-sca//modules/cluster/nlb"
  project_id             = var.project_id
  region                 = var.region
  subnet                 = var.external_subnet
  prefix                 = "ext-l3"
  instance_groups        = module.bigip-cluster.instance_groups
  target_service_account = var.bigip-sa
  address                = var.reserved_external_nlb_address
  protocols              = [
    "L3_DEFAULT",
  ]
}
```

## Resources managed by module

* HTTP health check that probes for active VMs to receive traffic
* Backend services for TCP and/or UDP, using existing instance groups as targets
* Forwarding rules for TCP and/or UDP that target the backend services created
  above, optionally using the provided IPv4 address.
* Firewall rules to allow ingress from GCP health check sources

## Resources **NOT** managed by module

* Firewall rules to allow ingress to targets; e.g. to allow VMs on network to
  send traffic through thi NLB to backend services an INGRESS
  [firewall rule](https://cloud.google.com/vpc/docs/using-firewalls#creating_firewall_rules)
  *MUST* be created
* Target services *MUST* be configured to handle traffic matching the source address
  of the NLB for data plane
* Target services *MUST* be configured to respond to health probes matching the source
  address of the NLB and on the health check port specified (default is 40000) -
  failure to respond with HTTP 200 status will cause the NLB to ignore the target
  service.
* NLB IPv4 address reservation; it is *RECOMMENDED* that a static IPv4 address
  be reserved outside of this module, and provided as an input.

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
| [google_compute_firewall.nlb](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_firewall) | resource |
| [google_compute_forwarding_rule.nlb](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_forwarding_rule) | resource |
| [google_compute_region_backend_service.service](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_region_backend_service) | resource |
| [google_compute_region_health_check.livez](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_region_health_check) | resource |
| [google_compute_subnetwork.subnet](https://registry.terraform.io/providers/hashicorp/google/latest/docs/data-sources/compute_subnetwork) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_instance_groups"></a> [instance\_groups](#input\_instance\_groups) | The set of instance groups that will become the backend services for the Network<br>load balancer. | `set(string)` | n/a | yes |
| <a name="input_prefix"></a> [prefix](#input\_prefix) | The prefix to use when naming resources managed by this module. Must be RFC1035<br>compliant and between 1 and 52 characters in length, inclusive. | `string` | n/a | yes |
| <a name="input_project_id"></a> [project\_id](#input\_project\_id) | The GCP project identifier where the BIG-IP cluster will be created | `string` | n/a | yes |
| <a name="input_region"></a> [region](#input\_region) | The compute region where where the resources will be deployed. | `string` | n/a | yes |
| <a name="input_subnet"></a> [subnet](#input\_subnet) | The fully-qualified subnetwork self-link that the health check firewall rule will<br>be applied to. | `string` | n/a | yes |
| <a name="input_target_service_account"></a> [target\_service\_account](#input\_target\_service\_account) | The email address of the service account which will be used for BIG-IP instances,<br>and used to apply ingress firewall rules for health checks. | `string` | n/a | yes |
| <a name="input_address"></a> [address](#input\_address) | The IPv4 address to use with the forwarding rule. | `string` | `null` | no |
| <a name="input_health_check_params"></a> [health\_check\_params](#input\_health\_check\_params) | Set the Network load balancer health check parameters that will be used to direct<br>incoming traffic to a BIG-IP or NGINX instance for initial handling. | <pre>object({<br>    check_interval_sec  = number<br>    timeout_sec         = number<br>    healthy_threshold   = number<br>    unhealthy_threshold = number<br>    port                = number<br>    request_path        = string<br>    response            = string<br>  })</pre> | <pre>{<br>  "check_interval_sec": 5,<br>  "healthy_threshold": 2,<br>  "port": 40000,<br>  "request_path": "/",<br>  "response": "OK",<br>  "timeout_sec": 2,<br>  "unhealthy_threshold": 2<br>}</pre> | no |
| <a name="input_labels"></a> [labels](#input\_labels) | An optional map of string key:value pairs to assign to created resources. | `map(string)` | `{}` | no |
| <a name="input_protocols"></a> [protocols](#input\_protocols) | The IP protocols that will be enabled in the network load balancer.<br><br>Default value is ["TCP", "UDP"]. | `set(string)` | <pre>[<br>  "TCP",<br>  "UDP"<br>]</pre> | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_addresses"></a> [addresses](#output\_addresses) | A list of unique forwarding-rule IPv4 and/or IPv6 addresses. |
| <a name="output_protocol_addresses"></a> [protocol\_addresses](#output\_protocol\_addresses) | A map of protocols to Network load balancer IPv4 and/or IPv6 address. |
| <a name="output_self_links"></a> [self\_links](#output\_self\_links) | A map of  protocols to fully-qualified Network load balancer self-links. |
<!-- END OF PRE-COMMIT-TERRAFORM DOCS HOOK -->
<!-- markdownlint-enable no-inline-html no-bare-urls -->
