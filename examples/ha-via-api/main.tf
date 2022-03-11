terraform {
  required_version = ">= 0.14.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 3.85"
    }
  }
}

locals {
  subnet = distinct([for subnet in var.external_subnet_ids : subnet[0].subnet_id if subnet[0].subnet_id != null])[0]
  region = distinct([for zone in var.zones : regex("^([a-z]{2,}-[a-z]+[0-9])-[a-z]$", zone)[0]])[0]
}

resource "google_compute_address" "ext" {
  project      = var.project_id
  name         = format("%s-ext", var.prefix)
  description  = "Static IP address for BIG-IP public ingress via forwarding-rule"
  address_type = "EXTERNAL"
  region       = local.region
}

module "ha" {
  source                            = "github.com/f5devcentral/terraform-google-f5-bigip-ha?ref=v1.0.0"
  prefix                            = var.prefix
  project_id                        = var.project_id
  zones                             = var.zones
  machine_type                      = var.machine_type
  image                             = var.image
  mgmt_subnet_ids                   = var.mgmt_subnet_ids
  external_subnet_ids               = var.external_subnet_ids
  internal_subnet_ids               = var.internal_subnet_ids
  gcp_secret_manager_authentication = true
  gcp_secret_name                   = var.gcp_secret_name
  labels                            = var.labels
  service_account                   = var.service_account
  f5_ssh_publickey                  = var.f5_ssh_publickey
  # Forwarding-rules are associated with target instances, not groups
  targets = {
    groups    = false
    instances = true
  }
}

module "forwarding-rule" {
  source     = "github.com/f5devcentral/terraform-google-f5-bigip-ha//modules/forwarding-rule?ref=v1.0.0"
  prefix     = var.prefix
  project_id = var.project_id
  address    = google_compute_address.ext.address
  region     = local.region
  targets    = module.ha.target_instances
  labels     = var.labels
  subnet     = local.subnet
}
