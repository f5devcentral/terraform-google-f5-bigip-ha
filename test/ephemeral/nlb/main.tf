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

module "ha" {
  source                            = "../../../"
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
  targets = {
    groups    = true
    instances = false
  }
}

module "nlb" {
  source                 = "../../../modules/nlb/"
  prefix                 = var.prefix
  project_id             = var.project_id
  region                 = local.region
  instance_groups        = module.ha.target_groups
  labels                 = var.labels
  target_service_account = var.service_account
  subnet                 = local.subnet
}
