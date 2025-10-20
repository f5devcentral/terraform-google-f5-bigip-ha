terraform {
  required_version = ">= 1.2"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
    http = {
      source  = "hashicorp/http"
      version = ">= 3.4"
    }
    local = {
      source  = "hashicorp/local"
      version = ">= 2.4"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.6"
    }
    tls = {
      source  = "hashicorp/tls"
      version = ">= 4.0"
    }
  }
}

locals {
  vpcs = merge({
    external   = "10.0.0.0/15"
    management = "10.100.0.0/15"
    }, { for i in range(0, 6) : format("internal-%d", i) => format("10.%d.0.0/15", 10 * i + 10) }
  )
}

data "google_compute_zones" "zones" {
  project = var.project_id
  region  = var.region
  status  = "UP"
}

data "http" "test_address" {
  url = "https://checkip.amazonaws.com"
  lifecycle {
    postcondition {
      condition     = self.status_code == 200
      error_message = "Failed to get local IP address."
    }
  }
}

resource "random_shuffle" "zones" {
  input = data.google_compute_zones.zones.names
}

resource "random_pet" "prefix" {
  length = 1
  keepers = {
    project = var.project_id
  }
}

# ATC tests need to know the BIG-IP password
resource "random_string" "password" {
  length           = 16
  upper            = true
  min_upper        = 1
  lower            = true
  min_lower        = 1
  numeric          = true
  min_numeric      = 1
  special          = true
  min_special      = 1
  override_special = "@#%&*()-_=+[]<>:?"
}

locals {
  labels = merge(var.labels, {
    purpose = "automated-testing"
    product = "terraform-google-f5-bigip-ha"
    driver  = "kitchen-terraform"
  })
}

resource "google_service_account" "sa" {
  project      = var.project_id
  account_id   = format("%s-bigip", random_pet.prefix.id)
  display_name = format("terraform-google-f5-bigip-ha test service account")
  description  = <<-EOD
A test service account for automated BIG-IP HA repo testing.
EOD
}

resource "google_project_iam_member" "sa" {
  for_each = toset([
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/monitoring.viewer",
  ])
  project = var.project_id
  role    = each.key
  member  = google_service_account.sa.member
  depends_on = [
    google_service_account.sa,
  ]
}

# Generate an SSH keypair
resource "tls_private_key" "ssh" {
  algorithm = "RSA"
  rsa_bits  = "4096"
}

resource "local_file" "test_privkey" {
  filename        = format("${path.module}/%s-ssh", random_pet.prefix.id)
  file_permission = "0600"
  content         = trimspace(tls_private_key.ssh.private_key_pem)
  depends_on = [
    tls_private_key.ssh,
  ]
}

resource "local_file" "test_pubkey" {
  filename        = format("${path.module}/%s-ssh.pub", random_pet.prefix.id)
  file_permission = "0640"
  content         = trimspace(tls_private_key.ssh.public_key_openssh)
  depends_on = [
    tls_private_key.ssh,
  ]
}

# Create VPC networks each with a single subnet
module "vpcs" {
  for_each    = local.vpcs
  source      = "memes/multi-region-private-network/google"
  version     = "3.0.0"
  project_id  = var.project_id
  name        = format("%s-%s", random_pet.prefix.id, each.key)
  description = format("BIG-IP HA module testing VPC (%s-%s)", random_pet.prefix.id, each.key)
  regions = [
    var.region,
  ]
  cidrs = {
    primary_ipv4_cidr          = each.value
    primary_ipv4_subnet_size   = 16
    primary_ipv4_subnet_offset = 0
    primary_ipv4_subnet_step   = 1
    primary_ipv6_cidr          = null
    secondaries                = null
  }
  options = {
    delete_default_routes = false
    flow_logs             = true
    ipv6_ula              = false
    mtu                   = 1460
    nat                   = each.key == "1"
    nat_logs              = true
    nat_tags              = null
    private_apis          = false
    restricted_apis       = false
    routing_mode          = "GLOBAL"
  }
}

# Grant access to management interface for SSH and HTTPS
resource "google_compute_firewall" "admin" {
  project       = var.project_id
  name          = format("%s-allow-admin", random_pet.prefix.id)
  network       = module.vpcs["management"].self_link
  description   = "BIG-IP administration on control-plane network"
  direction     = "INGRESS"
  source_ranges = coalescelist(var.admin_source_cidrs, [format("%s/32", trimspace(data.http.test_address.response_body))])
  target_service_accounts = [
    google_service_account.sa.email,
  ]
  allow {
    protocol = "tcp"
    ports = [
      22,
      443,
    ]
  }
  depends_on = [
    module.vpcs
  ]
}

# Generate a harness.tfvars file that will be used to seed fixtures
resource "local_file" "harness_tfvars" {
  filename = "${path.module}/harness.tfvars"
  content  = <<-EOT
project_id       = "${var.project_id}"
service_account  = "${google_service_account.sa.email}"
admin_password      = "${random_string.password.result}"
ssh_publickey =  "${trimspace(tls_private_key.ssh.public_key_openssh)}"
labels           = ${jsonencode(local.labels)}
EOT
  depends_on = [
    google_service_account.sa,
    local_file.test_privkey,
    local_file.test_pubkey,
    module.vpcs,
    google_compute_firewall.admin,
  ]
}
