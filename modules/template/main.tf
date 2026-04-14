terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 7.1"
    }
  }
}

data "google_compute_subnetwork" "subnets" {
  for_each  = var.interfaces == null ? {} : { for i, v in var.interfaces : tostring(i) => v.subnet_id }
  self_link = each.value
}

data "google_compute_image" "bigip" {
  project = try(regex("projects/([^/]+)/global/", var.image)[0], var.project_id)
  family  = try(regex("family/([^/]+)$", var.image)[0], null)
  name    = try(regex("images/([^/]+)$", var.image)[0], null)
}

locals {
  region = one(distinct([for subnet in data.google_compute_subnetwork.subnets : subnet.region]))
  user_data = templatefile(format("%s/templates/cloud-config.yaml", path.module), {
    onboard_sh                = base64gzip(file(format("%s/files/onboard.sh", path.module)))
    reset_management_route_sh = base64gzip(file(format("%s/files/reset_management_route.sh", path.module)))
    onboard_env = {
      MGMT_INTERFACE         = var.management_interface_index
      RUNTIME_INIT_URL       = try(var.runtime_init_installer.url, "")
      RUNTIME_INIT_SHA256SUM = try(var.runtime_init_installer.sha256sum, "")
      RUNTIME_INIT_INSTALLER_EXTRA_ARGS = trimspace(join(" ", compact(concat([
        try(var.runtime_init_installer.skip_toolchain_metadata_sync, false) ? "--skip-toolchain-metadata-sync" : "",
        try(var.runtime_init_installer.skip_verify, false) ? "--skip-verify" : "",
        coalesce(try(var.runtime_init_installer.verify_gpg_key_url, "unspecified"), "unspecified") != "unspecified" ? format("--key %s", var.runtime_init_installer.verify_gpg_key_url) : "",
      ]))))
      RUNTIME_INIT_EXTRA_ARGS = trimspace(join(" ", compact(concat([
        try(var.runtime_init_installer.skip_telemetry, false) ? "--skip-telemetry" : "",
      ]))))
    }
    reset_management_route_env = {
      MGMT_INTERFACE = var.management_interface_index
    }
    runtime_init_configs = { for i, config in [var.runtime_init_config] : (format("/config/cloud/%02d_runtime-init-conf.%s", i, can(jsondecode(config)) ? "json" : "yaml")) => config }
  })
  metadata = var.metadata == null ? {
    user-data = local.user_data
    } : merge({
      user-data = local.user_data
  }, var.metadata)
  # Official published images have a common naming convention that can be used to infer the release
  inferred_version = can(regex("f5-bigip-([12][0-9])-([0-9]+)-([0-9]+)-", data.google_compute_image.bigip.name)) ? format("v%s", join(".", regex("f5-bigip-([12][0-9])-([0-9]+)-([0-9]+)-", data.google_compute_image.bigip.name))) : "unknown version"
}


resource "google_compute_instance_template" "bigip" {
  project              = var.project_id
  name_prefix          = var.prefix
  description          = coalesce(var.description, format("%d-nic BIG-IP instance template for %s", length(data.google_compute_subnetwork.subnets), local.inferred_version))
  instance_description = coalesce(var.instance_description, format("%d-nic BIG-IP %s", length(data.google_compute_subnetwork.subnets), local.inferred_version))
  region               = local.region
  labels               = var.labels
  metadata             = local.metadata
  machine_type         = var.machine_type
  min_cpu_platform     = var.min_cpu_platform

  scheduling {
    automatic_restart   = var.preemptible ? false : var.automatic_restart
    on_host_maintenance = var.preemptible ? "TERMINATE" : "MIGRATE"
    preemptible         = var.preemptible
  }

  service_account {
    email = var.service_account
    scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
    ]
  }

  disk {
    device_name  = "boot-disk"
    auto_delete  = true
    boot         = true
    source_image = data.google_compute_image.bigip.self_link
    disk_type    = var.disk_type
    disk_size_gb = var.disk_size_gb
    labels       = var.labels
  }

  can_ip_forward = true
  tags           = var.network_tags

  dynamic "network_interface" {
    for_each = data.google_compute_subnetwork.subnets
    content {
      subnetwork = network_interface.value.self_link
      nic_type   = coalesce(try(var.interfaces[network_interface.key].nic_type, null), "VIRTIO_NET")
      dynamic "access_config" {
        for_each = tobool(coalesce(try(var.interfaces[network_interface.key].public_ip, null), "false")) ? { public = true } : {}
        content {}
      }
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}
