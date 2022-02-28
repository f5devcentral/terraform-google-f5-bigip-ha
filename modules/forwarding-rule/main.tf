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
  # Make sure each forwarding rule goes to the same target instance
  target = element(tolist(var.targets), 0)
}
data "google_compute_subnetwork" "subnet" {
  count     = var.is_external ? 0 : 1
  self_link = var.subnet
}

# Create a forwarding rule for each protocol that uses the reserved IP address.
resource "google_compute_forwarding_rule" "fwd" {
  for_each              = var.protocols
  project               = var.project_id
  name                  = replace(format("%s-%s", var.prefix, lower(each.key)), "_", "-")
  region                = var.region
  ip_address            = var.address
  ip_protocol           = each.value
  all_ports             = true
  load_balancing_scheme = var.is_external ? "EXTERNAL" : "INTERNAL"
  network               = var.is_external ? null : data.google_compute_subnetwork.subnet[0].network
  subnetwork            = var.is_external ? null : data.google_compute_subnetwork.subnet[0].id
  labels                = var.labels
  target                = local.target
}
