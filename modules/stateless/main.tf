terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 7.1"
    }
  }
}

data "google_compute_instance_template" "template" {
  self_link_unique = can(regex("\\?uniqueId=[0-9]+$", var.instance_template)) ? var.instance_template : null
  project          = try(regex("projects/([^/]+)/global/", var.instance_template)[0], var.project_id)
  name             = can(regex("\\?uniqueId=[0-9]+$", var.instance_template)) ? null : try(regex("global/instanceTemplates/(.*)$", var.instance_template)[0], null)
}

data "google_compute_subnetwork" "external" {
  self_link = data.google_compute_instance_template.template.network_interface[0].subnetwork
}

data "google_compute_zones" "zones" {
  project = var.project_id
  region  = data.google_compute_subnetwork.external.region
}

locals {
  metadata = try(length(var.metadata), 0) == 0 ? null : merge(
    data.google_compute_instance_template.template.metadata,
    var.metadata,
  )
  labels = try(length(var.labels), 0) == 0 ? null : merge(
    data.google_compute_instance_template.template.metadata,
    var.metadata,
  )
}

resource "google_compute_health_check" "livez" {
  for_each            = coalesce(try(var.health_check.self_link, null), "unspecified") == "unspecified" ? { create = true } : {}
  project             = var.project_id
  name                = format("%s-livez", var.prefix)
  check_interval_sec  = 60
  timeout_sec         = 2
  healthy_threshold   = 2
  unhealthy_threshold = 3
  http_health_check {
    port               = try(var.health_check.port, 26000)
    request_path       = "/"
    response           = "OK"
    port_specification = "USE_FIXED_PORT"
  }
}

# MIG health checks require access to BIG-IP nic0 interface.
resource "google_compute_firewall" "livez" {
  for_each    = try(var.health_check.port, null) == null ? {} : { create = true }
  project     = data.google_compute_subnetwork.external.project
  name        = format("%s-allow-livez", var.prefix)
  network     = data.google_compute_subnetwork.external.network
  description = "Allow liveness check for MIG"
  direction   = "INGRESS"
  source_ranges = [
    "35.191.0.0/16",
    "130.211.0.0/22",
  ]
  target_service_accounts = [for sa in data.google_compute_instance_template.template.service_account : sa.email]
  allow {
    protocol = "tcp"
    ports = [
      try(var.health_check.port, 26000),
    ]
  }
}

resource "google_compute_region_instance_group_manager" "mig" {
  project                          = var.project_id
  name                             = var.prefix
  description                      = var.description
  base_instance_name               = var.prefix
  region                           = data.google_compute_subnetwork.external.region
  target_size                      = var.num_instances
  wait_for_instances               = false
  distribution_policy_zones        = try(length(var.zones), 0) > 0 ? var.zones : null
  distribution_policy_target_shape = "EVEN"

  all_instances_config {
    metadata = local.metadata
    labels   = local.labels
  }

  version {
    instance_template = data.google_compute_instance_template.template.self_link_unique
  }

  update_policy {
    type                           = "OPPORTUNISTIC"
    minimal_action                 = "REPLACE"
    most_disruptive_allowed_action = "REPLACE"
    instance_redistribution_type   = "NONE"
    max_surge_fixed                = length(coalescelist(var.zones, data.google_compute_zones.zones.names))
    max_unavailable_fixed          = 0
    replacement_method             = "SUBSTITUTE"
  }

  auto_healing_policies {
    health_check      = one(compact(concat([for hc in google_compute_health_check.livez : hc.id], [try(var.health_check.self_link, null)])))
    initial_delay_sec = compact(concat([try(var.health_check.initial_delay_sec, null)], [600]))[0]
  }

  instance_lifecycle_policy {
    force_update_on_repair    = "YES"
    default_action_on_failure = "REPAIR"
  }

  dynamic "named_port" {
    for_each = var.named_ports == null ? {} : var.named_ports
    content {
      name = named_port.key
      port = named_port.value
    }
  }

  lifecycle {
    ignore_changes = [
      target_size,
    ]
  }
}
