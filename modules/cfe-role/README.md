# CFE-Role sub-module

This Terraform module is a helper to create a custom IAM role that has the
minimal permissions required for Cloud Failover Extension to function correctly.
The role will be created in the specified project by default, but can be created
as an *Organization role* if preferred, for reuse across projects.

Unless a specific identifier is provided in the `id` variable, a semi-random
identifier will be generated of the form `bigip_cfe_xxxxxxxxxx` to avoid unique
identifier collisions during the time after a custom role is deleted but before
it is purged from the project or organization.

> **NOTE:** This module is unsupported and not an official F5 product. If you
> require assistance please join our
> [Slack GCP channel](https://f5cloudsolutions.slack.com/messages/gcp) and ask!

## Examples

### Create the custom role at the project, and assign to a BIG-IP service account

<!-- spell-checker: disable -->
```hcl
module "cfe_role" {
  source    = "memes/f5-bigip/google//modules/cfe-role"
  version   = "2.0.2"
  target_id = "my-project-id"
  members   = ["serviceAccount:bigip@my-project-id.iam.gserviceaccount.com"]
}
```
<!-- spell-checker: enable -->

### Create the custom role for entire org, but do not explicitly assign membership

<!-- spell-checker: disable -->
```hcl
module "cfe_org_role" {
  source      = "memes/f5-bigip/google//modules/cfe-role"
  version     = "2.0.2"
  target_type = "org"
  target_id   = "my-org-id"
}
```
<!-- spell-checker: enable -->

### Create the custom role in the project with a fixed id, and assign to a BIG-IP service account

<!-- spell-checker: disable -->
```hcl
module "cfe_role" {
  source    = "memes/f5-bigip/google//modules/cfe-role"
  version   = "2.0.2"
  id = "my_custom_role"
  target_id = "my-project-id"
  members   = ["serviceAccount:bigip@my-project-id.iam.gserviceaccount.com"]
}
```
<!-- spell-checker: enable -->
<!-- markdownlint-disable MD033 MD034 -->
<!-- BEGINNING OF PRE-COMMIT-TERRAFORM DOCS HOOK -->
<!-- END OF PRE-COMMIT-TERRAFORM DOCS HOOK -->
<!-- markdownlint-enable MD033 MD034 -->
