terraform {
  required_version = ">= 0.14.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 3.85"
    }
  }
}

# Upstream module *requires* setting parameters on the provider
provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  prefix = format("%s-%s", var.prefix, var.test_prefix)
  mgmt_subnet_ids = [for i in range(0, 2) : [{
    subnet_id          = var.subnets[1]
    public_ip          = var.public_mgmt
    private_ip_primary = null
  }]]
  external_subnet_ids = [for i in range(0, 2) : [{
    subnet_id            = var.subnets[0]
    public_ip            = var.public_external
    private_ip_primary   = null
    private_ip_secondary = null
  }]]
  internal_subnet_ids = [for i in range(0, 2) : var.num_nics > 2 ? [for j in range(2, var.num_nics) : {
    subnet_id          = var.subnets[j]
    public_ip          = false
    private_ip_primary = null
    }] : [{
    subnet_id          = null,
    public_ip          = null,
    private_ip_primary = null
  }]]
}

module "test" {
  source              = "./../../../ephemeral/ilb/"
  prefix              = local.prefix
  project_id          = var.project_id
  zones               = var.zones
  machine_type        = var.machine_type
  image               = var.image
  mgmt_subnet_ids     = local.mgmt_subnet_ids
  external_subnet_ids = local.external_subnet_ids
  internal_subnet_ids = local.internal_subnet_ids
  gcp_secret_name     = var.secret_key
  labels              = var.labels
  service_account     = var.bigip_sa
  f5_ssh_publickey    = var.ssh_pubkey_file
  sleep_time          = var.sleep_time
}
