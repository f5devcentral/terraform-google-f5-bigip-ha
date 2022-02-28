terraform {
  required_version = ">= 0.14.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 3.85"
    }
    local = {
      source  = "hashicorp/local"
      version = ">= 2.1.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.1.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = ">= 3.1.0"
    }
  }
}

data "google_compute_zones" "zones" {
  project = var.project_id
  region  = var.region
  status  = "UP"
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
resource "random_password" "bigip_password" {
  length           = 16
  upper            = true
  min_upper        = 1
  lower            = true
  min_lower        = 1
  number           = true
  min_numeric      = 1
  special          = true
  min_special      = 1
  override_special = "@#%&*()-_=+[]<>:?"
}

locals {
  prefix = random_pet.prefix.id
  # Generated service account email address is predictable - use it directly
  bigip_sa = format("%s-bigip@%s.iam.gserviceaccount.com", local.prefix, var.project_id)
  labels = merge(var.labels, {
    purpose = "automated-testing"
    product = "terraform-google-f5-bigip-ha"
    driver  = "kitchen-terraform"
  })
}

module "bigip_sa" {
  source     = "terraform-google-modules/service-accounts/google"
  version    = "4.1.0"
  project_id = var.project_id
  prefix     = local.prefix
  names      = ["bigip"]
  descriptions = [
    "BIG-IP automated test service account",
  ]
  project_roles = [
    "${var.project_id}=>roles/logging.logWriter",
    "${var.project_id}=>roles/monitoring.metricWriter",
    "${var.project_id}=>roles/monitoring.viewer",
  ]
  generate_keys = false
}

module "password" {
  source     = "memes/secret-manager/google"
  version    = "1.0.5"
  project_id = var.project_id
  id         = format("%s-bigip-admin-key", local.prefix)
  secret     = random_password.bigip_password.result
  accessors = [
    # Generated service account email address is predictable - use it directly
    format("serviceAccount:%s", local.bigip_sa),
  ]
  depends_on = [
    module.bigip_sa,
  ]
}

# Generate an SSH keypair
resource "tls_private_key" "ssh" {
  algorithm = "RSA"
  rsa_bits  = "4096"
}

resource "local_file" "test_privkey" {
  filename        = format("${path.module}/%s-ssh", local.prefix)
  file_permission = "0600"
  content         = tls_private_key.ssh.private_key_pem
}

resource "local_file" "test_pubkey" {
  filename        = format("${path.module}/%s-ssh.pub", local.prefix)
  file_permission = "0640"
  content         = tls_private_key.ssh.public_key_openssh
}

# Create 8 VPC networks, each with a single subnet
module "vpcs" {
  for_each                               = { for i, v in ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta"] : i => v }
  source                                 = "terraform-google-modules/network/google"
  version                                = "4.1.0"
  project_id                             = var.project_id
  network_name                           = format("%s-%s", local.prefix, each.value)
  description                            = format("BIG-IP HA module testing VPC (%s-%d)", local.prefix, each.key)
  auto_create_subnetworks                = false
  delete_default_internet_gateway_routes = false
  mtu                                    = 1460
  routing_mode                           = "REGIONAL"
  subnets = [
    {
      subnet_name           = format("%s-%s", local.prefix, each.value)
      subnet_ip             = cidrsubnet("172.16.0.0/12", 4, each.key)
      subnet_region         = var.region
      subnet_private_access = false
    }
  ]
}

module "nat" {
  source      = "terraform-google-modules/cloud-router/google"
  version     = "1.3.0"
  project     = var.project_id
  region      = var.region
  name        = module.vpcs[1].network_name
  description = format("BIG-IP HA module testing NAT (%s)", local.prefix)
  network     = module.vpcs[1].network_self_link
  nats = [
    {
      name = module.vpcs[1].network_name
    }
  ]
  depends_on = [
    module.vpcs
  ]
}

# Grant access to management interface for SSH and HTTPS
resource "google_compute_firewall" "admin" {
  project       = var.project_id
  name          = format("%s-allow-admin", local.prefix)
  network       = module.vpcs[1].network_self_link
  description   = "BIG-IP administration on control-plane network"
  direction     = "INGRESS"
  source_ranges = var.admin_source_cidrs
  target_service_accounts = [
    local.bigip_sa,
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
prefix     = "${local.prefix}"
project_id = "${var.project_id}"
region = "${var.region}"
zones      = ${jsonencode(random_shuffle.zones.result)}
bigip_sa   = "${local.bigip_sa}"
secret_key = "${module.password.secret_id}"
bigip_password = "${random_password.bigip_password.result}"
ssh_pubkey_file = "${abspath(local_file.test_pubkey.filename)}"
subnets = ${jsonencode([for i in range(0, 8) : module.vpcs[tostring(i)].subnets_self_links[0]])}
labels = ${jsonencode(local.labels)}
EOT
}
