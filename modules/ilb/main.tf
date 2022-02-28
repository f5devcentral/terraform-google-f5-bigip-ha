terraform {
  required_version = ">= 0.14.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 3.85"
    }
  }
}

data "google_compute_subnetwork" "subnet" {
  self_link = var.subnet
}

resource "google_compute_region_health_check" "livez" {
  project             = var.project_id
  name                = format("%s-livez", var.prefix)
  region              = var.region
  check_interval_sec  = var.health_check_params.check_interval_sec
  timeout_sec         = var.health_check_params.timeout_sec
  healthy_threshold   = var.health_check_params.healthy_threshold
  unhealthy_threshold = var.health_check_params.unhealthy_threshold
  http_health_check {
    port               = var.health_check_params.port
    request_path       = var.health_check_params.request_path
    response           = var.health_check_params.response
    port_specification = "USE_FIXED_PORT"
  }
}

resource "google_compute_region_backend_service" "service" {
  for_each              = var.protocols
  project               = var.project_id
  name                  = replace(format("%s-%s", var.prefix, lower(each.value)), "_", "-")
  region                = var.region
  protocol              = each.value
  load_balancing_scheme = "INTERNAL"
  network               = data.google_compute_subnetwork.subnet.network
  health_checks = [
    google_compute_region_health_check.livez.id,
  ]
  dynamic "backend" {
    for_each = var.instance_groups
    content {
      group = backend.value
    }
  }
}

resource "google_compute_forwarding_rule" "ilb" {
  for_each              = var.protocols
  project               = var.project_id
  name                  = replace(format("%s-%s", var.prefix, lower(each.value)), "_", "-")
  region                = var.region
  ip_address            = var.address
  ip_protocol           = each.value
  all_ports             = true
  allow_global_access   = var.global_access
  load_balancing_scheme = "INTERNAL"
  network               = data.google_compute_subnetwork.subnet.network
  subnetwork            = data.google_compute_subnetwork.subnet.id
  labels                = var.labels
  backend_service       = google_compute_region_backend_service.service[each.value].id
}

resource "google_compute_firewall" "ilb" {
  project = var.project_id
  name    = format("%s-allow-hc", var.prefix)
  network = data.google_compute_subnetwork.subnet.network
  source_ranges = [
    "35.191.0.0/16",
    "130.211.0.0/22",
  ]
  target_service_accounts = [
    var.target_service_account,
  ]
  allow {
    protocol = "TCP"
    ports = [
      var.health_check_params.port,
    ]
  }
}
