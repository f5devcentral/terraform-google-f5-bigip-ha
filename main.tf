terraform {
  required_version = ">= 0.14.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 3.85.0"
    }
  }
}

locals {
  num_bigips       = 2
  dsc_data_subnets = toset(coalescelist(compact([for outer in var.internal_subnet_ids : length(outer) > 0 ? outer[0].subnet_id : null]), compact([for outer in var.external_subnet_ids : length(outer) > 0 ? outer[0].subnet_id : null])))
  /*
  dsc_subnet = element(distinct(compact(concat([for subnet in var.internal_subnet_ids: subnet.subnet_id], [for subnet in var.external_subnet_ids: subnet.subnet_id]))), 0)
  dsc_subnet_is_internal = element(distinct(compact(concat([for subnet in var.internal_subnet_ids: "internal" if coalesce(subnet.subnet_id, "unspecified") != "unspecified"], [for subnet in var.external_subnet_ids: "external" if coalesce(subnet.subnet_id, "unspecified") != "unspecified"]))), 0) == "internal"
  external_subnet_ids = local.dsc_subnet_is_internal ? var.external_subnet_ids : [for i, v in var.external_subnet_ids: merge(v, {
    private_ip_primary = google_compute_address.dsc[i].address
  })]
  internal_subnet_ids = local.dsc_subnet_is_internal ? [for i, v in var.internal_subnet_ids: merge(v, {
    private_ip_primary = google_compute_address.dsc[i].address
  })] : var.internal_subnet_ids
  */
}

module "instances" {
  for_each = { for i in range(0, local.num_bigips) : "${i}" => {
    zone                = element(var.zones, i)
    mgmt_subnet_ids     = element(var.mgmt_subnet_ids, i)
    external_subnet_ids = element(var.external_subnet_ids, i)
    internal_subnet_ids = element(var.internal_subnet_ids, i)
  } }
  source                            = "F5Networks/bigip-module/gcp"
  version                           = "1.1.18"
  prefix                            = var.prefix
  project_id                        = var.project_id
  zone                              = each.value.zone
  min_cpu_platform                  = var.min_cpu_platform
  machine_type                      = var.machine_type
  automatic_restart                 = var.automatic_restart
  preemptible                       = var.preemptible
  image                             = var.image
  disk_type                         = var.disk_type
  disk_size_gb                      = var.disk_size_gb
  mgmt_subnet_ids                   = each.value.mgmt_subnet_ids
  external_subnet_ids               = each.value.external_subnet_ids
  internal_subnet_ids               = each.value.internal_subnet_ids
  f5_username                       = var.f5_username
  f5_password                       = var.f5_password
  onboard_log                       = var.onboard_log
  libs_dir                          = var.libs_dir
  gcp_secret_manager_authentication = var.gcp_secret_manager_authentication
  gcp_secret_name                   = var.gcp_secret_name
  gcp_secret_version                = var.gcp_secret_version
  DO_URL                            = var.DO_URL
  AS3_URL                           = var.AS3_URL
  TS_URL                            = var.TS_URL
  CFE_URL                           = var.CFE_URL
  FAST_URL                          = var.FAST_URL
  INIT_URL                          = var.INIT_URL
  labels                            = var.labels
  service_account                   = var.service_account
  f5_ssh_publickey                  = var.f5_ssh_publickey
  custom_user_data                  = var.custom_user_data
  metadata                          = var.metadata
  sleep_time                        = var.sleep_time
}


resource "google_compute_instance_group" "group" {
  for_each    = { for k, v in module.instances : v.zone => v.self_link... if var.targets.groups }
  project     = var.project_id
  name        = format("%s-%02d", var.prefix, index(var.zones, each.key))
  description = format("BIG-IP instance group (%s %s)", var.prefix, each.key)
  zone        = each.key
  instances   = each.value
}

resource "google_compute_target_instance" "target" {
  for_each = { for i in range(0, local.num_bigips) : "${i}" => {
    name      = module.instances["${i}"].name
    zone      = module.instances["${i}"].zone
    self_link = module.instances["${i}"].self_link
  } if var.targets.instances }
  #for_each    = { for k, v in module.instances : v.name => { zone = v.zone, self_link = v.self_link } if var.targets.instances }
  project     = var.project_id
  name        = format("%s-tgt", each.value.name)
  description = format("BIG-IP %s target instance", each.value.name)
  zone        = each.value.zone
  instance    = each.value.self_link
}

data "google_compute_subnetwork" "dsc_mgmt" {
  for_each  = toset([for subnet in flatten(var.mgmt_subnet_ids) : subnet.subnet_id])
  self_link = each.value
}

data "google_compute_subnetwork" "dsc_data" {
  for_each  = local.dsc_data_subnets
  self_link = each.value
}

# DSC requires BIG-IP instances to communicate via HTTPS management port on
# control-plane network.
resource "google_compute_firewall" "mgt_sync" {
  for_each    = toset([for subnet in data.google_compute_subnetwork.dsc_mgmt : subnet.network])
  project     = var.project_id
  name        = format("%s-allow-dsc-mgmt", var.prefix)
  network     = each.value
  description = "BIG-IP ConfigSync for management network"
  direction   = "INGRESS"
  source_service_accounts = [
    var.service_account,
  ]
  target_service_accounts = [
    var.service_account,
  ]
  allow {
    protocol = "tcp"
    ports = [
      443,
    ]
  }
}

# DSC requires BIG-IP instances to communicate via known ports on data-plane
# network.
resource "google_compute_firewall" "data_sync" {
  for_each    = toset([for subnet in data.google_compute_subnetwork.dsc_data : subnet.network])
  project     = var.project_id
  name        = format("%s-allow-dsc-data", var.prefix)
  network     = each.value
  description = "BIG-IP ConfigSync for data-plane network"
  direction   = "INGRESS"
  source_service_accounts = [
    var.service_account,
  ]
  target_service_accounts = [
    var.service_account,
  ]
  allow {
    protocol = "tcp"
    ports = [
      443,
      4353,
      "6123-6128",
    ]
  }
  allow {
    protocol = "udp"
    ports = [
      1026,
    ]
  }
}
