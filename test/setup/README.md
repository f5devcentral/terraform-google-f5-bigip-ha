# Setup

The Terraform in this folder will be executed before creating resources and can
be used to setup service accounts, service principals, etc, that are used by the
inspec-* verifiers.

## Configuration

Create a local `terraform.tfvars` file that configures the testing project
constraints.

```hcl
# The GCP project identifier to use
project_id  = "my-gcp-project"

# The single Compute Engine region where the resources will be created
region = "us-west1"

```

<!-- markdownlint-disable MD033 MD034 -->
<!-- BEGINNING OF PRE-COMMIT-TERRAFORM DOCS HOOK -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 0.14.5 |
| <a name="requirement_google"></a> [google](#requirement\_google) | >= 3.85 |
| <a name="requirement_local"></a> [local](#requirement\_local) | >= 2.1.0 |
| <a name="requirement_random"></a> [random](#requirement\_random) | >= 3.1.0 |
| <a name="requirement_tls"></a> [tls](#requirement\_tls) | >= 3.1.0 |

## Modules

| Name | Source | Version |
|------|--------|---------|
| <a name="module_bigip_sa"></a> [bigip\_sa](#module\_bigip\_sa) | terraform-google-modules/service-accounts/google | 4.1.0 |
| <a name="module_nat"></a> [nat](#module\_nat) | terraform-google-modules/cloud-router/google | 1.3.0 |
| <a name="module_password"></a> [password](#module\_password) | memes/secret-manager/google | 1.0.5 |
| <a name="module_vpcs"></a> [vpcs](#module\_vpcs) | terraform-google-modules/network/google | 4.1.0 |

## Resources

| Name | Type |
|------|------|
| [google_compute_firewall.admin](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_firewall) | resource |
| [local_file.harness_tfvars](https://registry.terraform.io/providers/hashicorp/local/latest/docs/resources/file) | resource |
| [local_file.test_privkey](https://registry.terraform.io/providers/hashicorp/local/latest/docs/resources/file) | resource |
| [local_file.test_pubkey](https://registry.terraform.io/providers/hashicorp/local/latest/docs/resources/file) | resource |
| [random_password.bigip_password](https://registry.terraform.io/providers/hashicorp/random/latest/docs/resources/password) | resource |
| [random_pet.prefix](https://registry.terraform.io/providers/hashicorp/random/latest/docs/resources/pet) | resource |
| [random_shuffle.zones](https://registry.terraform.io/providers/hashicorp/random/latest/docs/resources/shuffle) | resource |
| [tls_private_key.ssh](https://registry.terraform.io/providers/hashicorp/tls/latest/docs/resources/private_key) | resource |
| [google_compute_zones.zones](https://registry.terraform.io/providers/hashicorp/google/latest/docs/data-sources/compute_zones) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_project_id"></a> [project\_id](#input\_project\_id) | GCP project id. | `string` | n/a | yes |
| <a name="input_region"></a> [region](#input\_region) | Compute engine region where resources will be created. | `string` | n/a | yes |
| <a name="input_admin_source_cidrs"></a> [admin\_source\_cidrs](#input\_admin\_source\_cidrs) | CIDRs permitted to access BIG-IP admin. Default is '0.0.0.0/0'. | `list(string)` | <pre>[<br>  "0.0.0.0/0"<br>]</pre> | no |
| <a name="input_labels"></a> [labels](#input\_labels) | Optional additional labels to apply to resources. | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_harness_tfvars"></a> [harness\_tfvars](#output\_harness\_tfvars) | The name of the generated harness.tfvars file that will be a common input to all<br>test fixtures. |
| <a name="output_ssh_privkey_path"></a> [ssh\_privkey\_path](#output\_ssh\_privkey\_path) | The full path to the private SSH key that will be used to verify remote shell<br>access. |
<!-- END OF PRE-COMMIT-TERRAFORM DOCS HOOK -->
<!-- markdownlint-enable MD033 MD034 -->
