terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 7.1"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.8"
    }
  }
}

data "google_compute_subnetwork" "external" {
  self_link = var.interfaces[0].subnet_id
}

provider "google" {
  # Apply a consistent set of labels to all resources that accept labels.
  default_labels = merge({
    module   = "terraform-google-f5-bigip-ha"
    scenario = "stateful-nlb"
  }, var.labels == null ? {} : var.labels)
}

# Reserve a public IPv4 address that will be the demo VIP; it will be assigned to the Google Cloud NLB's forwarding-rule
# and used as the virtual address in the BIG-IP service.
resource "google_compute_address" "vip" {
  project      = var.project_id
  name         = var.name
  description  = <<-EOD
    An example external public address for stateless-nlb example.
    EOD
  address_type = "EXTERNAL"
  ip_version   = "IPV4"
  network_tier = "PREMIUM"
  region       = var.region
}

# The module requires an explicit service account; this could be an existing SA such as the default compute service
# account, but the recommendation is to create a service account just for the BIG-IP workloads.
resource "google_service_account" "sa" {
  project      = var.project_id
  account_id   = var.name
  display_name = "BIG-IP Service Account for stateless-nlb example scenario"
  description  = <<-EOD
    An example service account for stateless-nlb example; this scenario does not require that the VMs have access to
    Google Cloud APIs, so it will not be bound to any permissions.
    EOD
  # NOTE: Setting this to true to support rapid iteration when testing
  create_ignore_already_exists = true
}

# Generate a random password for the BIG-IP administration.
resource "random_string" "admin_password" {
  length      = 16
  upper       = true
  min_upper   = 2
  lower       = true
  min_lower   = 2
  numeric     = true
  min_numeric = 2
  special     = true
  min_special = 2
  # Set the default set of special characters to those listed in https://my.f5.com/manage/s/article/K2873, excluding all
  # forms of quotation, apostrophe and backslash to avoid potential issues when quoting the string.
  override_special = "!$%^&*()~-+=[]{}:./<>|"
}

# Create a Secret Manager secret with random password for BIG-IP access. The BIG-IP service account will be permitted to
# retrieve the password.
module "admin_password" {
  source     = "memes/secret-manager/google"
  version    = "2.2.2"
  project_id = var.project_id
  id         = var.name
  secret     = null
  accessors = [
    google_service_account.sa.member,
  ]

  depends_on = [
    google_service_account.sa,
  ]
}

resource "google_secret_manager_secret_version" "admin_password" {
  secret      = module.admin_password.id
  secret_data = random_string.admin_password.result

  depends_on = [
    module.admin_password,
    random_string.admin_password,
  ]
}

# Define an instance template for the BIG-IP VMs that will be launched by a MIG.
module "bigip_ha" {
  source     = "git::https://github.com/f5devcentral/terraform-google-f5-bigip-ha?ref=v0.2.2"
  project_id = var.project_id
  prefix     = var.name

  # Provide per-instance metadata so that a single registration key goes to each BIG-IP VE instance.
  # NOTE: The instances variable can also be used to override naming, assign Alias IPs as secondary IPs, etc., but for
  # this example it will stick to the same naming convention and just add license key.
  instances = { for i in range(0, 2) : format("%s-%02d", var.name, i + 1) => {
    metadata = {
      bigip_license_key = var.license_keys[i]
    }
  } }

  # Use a bring-your-own-license (BYOL) image; the BIG-IP will be inactive until the license is applied by runtime-init.
  image = "projects/f5-7626-networks-public/global/images/f5-bigip-21-0-0-1-0-0-13-byol-ltm-1boot-loc-260128094804"

  # For consistent and predictable naming, it is important to set the common DNS domain name to use with instances; for
  # example 'your-domain.com'. Instances will be given the host name "{prefix}-0n.{host_domain}".
  # NOTE: BIG-IP hostnames have a limit of 65 characters.
  host_domain     = "example.com"
  description     = <<-EOD
  An example BIG-IP active-standby HA deployment for stateful-nlb scenario.
  EOD
  service_account = google_service_account.sa.email
  interfaces      = var.interfaces
  metadata        = var.metadata
  # This example builds a runtime-init configuration from a template file, substituting values as needed. For production
  # deployments this will most likely be a static file with lifecycle managed outside this module.
  runtime_init_config = templatefile(format("%s/templates/runtime-init-conf.yaml", path.module), {
    admin_pass_secret = module.admin_password.secret_id
    vip               = google_compute_address.vip.address
  })

  depends_on = [
    google_compute_address.vip,
    module.admin_password,
  ]
}

# This is the health check that the target pool uses to determine which managed instances receive traffic. This
# should correspond to a readyz virtual server declared that responds with 200 when the instance is ready to handle
# traffic distribution. It is expected that only the active VE in a group will respond with success.
resource "google_compute_http_health_check" "readyz" {
  project             = var.project_id
  name                = format("%s-readyz", var.name)
  check_interval_sec  = 10
  timeout_sec         = 1
  healthy_threshold   = 1
  unhealthy_threshold = 2
  # This port value must match the correspond readyz virtual server; see line 315 in example runtime-init-conf.yaml.
  port         = 26000
  request_path = "/"
}


# By default, Google Cloud imposes a default DENY ingress rule; to allow NLB health check probes to reach the BIG-IP a
# rule must be created on network attached to external interface (eth0).
resource "google_compute_firewall" "readyz" {
  project     = var.project_id
  name        = format("%s-allow-readyz", var.name)
  network     = data.google_compute_subnetwork.external.network
  description = "Allow NLB health check probes to hit BIG-IP instances."
  direction   = "INGRESS"
  source_ranges = [
    "35.191.0.0/16",
    "209.85.152.0/22",
    "209.85.204.0/22",
  ]
  target_service_accounts = [
    google_service_account.sa.email,
  ]
  allow {
    protocol = "tcp"
    ports = [
      # This port value must match the port used by the readyz check above, and corresponding readyz virtual server;
      # see line 303 in example runtime-init-conf.yaml.
      26000,
    ]
  }

  depends_on = [
    google_service_account.sa,
  ]
}


resource "google_compute_target_pool" "bigip" {
  project     = var.project_id
  name        = var.name
  description = <<-EOD
  F5 BIG-IP target pool for VEs in stateless-nlb example.
  EOD
  region      = var.region
  health_checks = [
    google_compute_http_health_check.readyz.self_link,
  ]
  instances = [for k, v in module.bigip_ha.self_links : v]

  depends_on = [
    module.bigip_ha,
  ]
}

resource "google_compute_forwarding_rule" "vip" {
  project               = var.project_id
  name                  = var.name
  description           = <<-EOD
    An example forwarding-rule that sends all TCP traffic to the BIG-IP managed instances.
    EOD
  region                = var.region
  target                = google_compute_target_pool.bigip.id
  ip_address            = google_compute_address.vip.id
  ip_protocol           = "TCP"
  all_ports             = true
  load_balancing_scheme = "EXTERNAL"

  depends_on = [
    google_compute_target_pool.bigip,
  ]
}


# By default, Google Cloud imposes a default DENY ingress rule; to allow BIG-IP instances to receive traffic from the
# public internet it must allow ingress from they must be allowed to connect to the VMs.
resource "google_compute_firewall" "public" {
  project       = var.project_id
  name          = format("%s-allow-bigip-ext", var.name)
  network       = data.google_compute_subnetwork.external.network
  description   = "Allow access to BIG-IP from sources on the internet"
  direction     = "INGRESS"
  source_ranges = coalescelist(var.allowlist_cidrs == null ? [] : var.allowlist_cidrs, ["0.0.0.0/0"])
  target_service_accounts = [
    google_service_account.sa.email,
  ]
  allow {
    protocol = "tcp"
    ports = [
      80,
      443,
    ]
  }
}
