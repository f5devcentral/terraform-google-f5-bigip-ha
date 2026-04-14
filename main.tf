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

data "google_compute_subnetwork" "subnets" {
  for_each  = var.interfaces == null ? {} : { for i, v in var.interfaces : tostring(i) => v.subnet_id }
  self_link = each.value
}

data "google_compute_image" "bigip" {
  project = try(regex("projects/([^/]+)/global/", var.image)[0], var.project_id)
  family  = try(regex("family/([^/]+)$", var.image)[0], null)
  name    = try(regex("images/([^/]+)$", var.image)[0], null)
}

data "google_compute_zones" "zones" {
  project = var.project_id
  region  = local.region
}

resource "random_shuffle" "zones" {
  input = data.google_compute_zones.zones.names
}

# Generate a pseudo-random tag value that can be used in firewall rules that are unique to this cluster of BIG-IPs.
resource "random_id" "cluster_tag" {
  prefix      = format("%s-", var.prefix)
  byte_length = 4
}

locals {
  dsc_data_plane_index = var.management_interface_index == 0 ? 1 : 0
  cluster_tag          = coalesce(var.cluster_network_tag, random_id.cluster_tag.hex)
  region               = one(distinct([for subnet in data.google_compute_subnetwork.subnets : subnet.region]))
  zones                = coalescelist(var.zones, random_shuffle.zones.result)
  user_data = templatefile(format("%s/modules/template/templates/cloud-config.yaml", path.module), {
    onboard_sh                = base64gzip(file(format("%s/modules/template/files/onboard.sh", path.module)))
    reset_management_route_sh = base64gzip(file(format("%s/modules/template/files/reset_management_route.sh", path.module)))
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
  vm_names         = try(length(var.instances), 0) > 0 ? keys(var.instances) : [for i in range(0, var.num_instances) : format("%s-%02d", var.prefix, i + 1)]
  vms = { for i, name in local.vm_names : name => {
    hostname = try(compact(concat(try([var.instances[name].hostname], []), coalesce(var.host_domain, "unspecified") == "unspecified" ? [] : [format("%s.%s", name, var.host_domain)]))[0], null)
    zone     = element(local.zones, i)
    metadata = merge(
      {
        bigip_ha_peer_name        = try(compact(concat(try([var.instances[local.vm_names[i == 0 ? 1 : 0]].hostname], []), coalesce(var.host_domain, "unspecified") == "unspecified" ? [local.vm_names[i == 0 ? 1 : 0]] : [format("%s.%s", local.vm_names[i == 0 ? 1 : 0], var.host_domain)]))[0])
        bigip_ha_peer_address     = coalesce(try(var.instances[local.vm_names[i == 0 ? 1 : 0]].interfaces[local.dsc_data_plane_index].primary_ip, ""), try(google_compute_address.dsc_data_plane[local.vm_names[i == 0 ? 1 : 0]].address, ""))
        bigip_ha_peer_owner_index = min(i, 1)
      },
      local.metadata,
      try(var.instances[name].metadata, {}),
    )
    interfaces = [for i, v in var.interfaces : {
      subnet_id = data.google_compute_subnetwork.subnets[tostring(i)].self_link
      public_ip = tobool(coalesce(
        try(v.public_ip, null),
        "false",
      ))
      nic_type = coalesce(
        try(v.nic_type, null),
        "VIRTIO_NET",
      )
      private_ip_primary = coalesce(
        try(var.instances[name].interfaces[i].primary_ip, null),
        i == var.management_interface_index ? try(google_compute_address.dsc_control_plane[name].address, null) : null,
        i == local.dsc_data_plane_index ? try(google_compute_address.dsc_data_plane[name].address, null) : null,
        "unspecified",
      )
      private_ip_secondary = try(var.instances[name].interfaces[i], {})
    }]
  } }
}

resource "google_compute_address" "dsc_control_plane" {
  for_each     = toset([for name in local.vm_names : name if coalesce(try(var.instances[name].interfaces[var.management_interface_index].primary_ip, null), "unspecified") == "unspecified"])
  name         = format("%s-dsc-cp", each.key)
  description  = format("Reserved control-plane address for BIG-IP instance %s", each.key)
  address_type = "INTERNAL"
  ip_version   = "IPV4"
  purpose      = "GCE_ENDPOINT"
  project      = var.project_id
  subnetwork   = data.google_compute_subnetwork.subnets[tostring(var.management_interface_index)].id
  region       = data.google_compute_subnetwork.subnets[tostring(var.management_interface_index)].region
  labels       = var.labels
}

resource "google_compute_address" "dsc_data_plane" {
  for_each     = toset([for name in local.vm_names : name if try(var.instances[name].interfaces[local.dsc_data_plane_index].primary_ip, "") == ""])
  name         = format("%s-dsc-dp", each.key)
  description  = format("Reserved data-plane address for BIG-IP instance %s", each.key)
  address_type = "INTERNAL"
  ip_version   = "IPV4"
  purpose      = "GCE_ENDPOINT"
  project      = var.project_id
  subnetwork   = data.google_compute_subnetwork.subnets[tostring(local.dsc_data_plane_index)].id
  region       = data.google_compute_subnetwork.subnets[tostring(local.dsc_data_plane_index)].region
  labels       = var.labels
}

resource "google_compute_instance" "bigip" {
  for_each         = local.vms
  project          = var.project_id
  name             = each.key
  description      = coalesce(var.description, format("%d-nic BIG-IP %s", length(data.google_compute_subnetwork.subnets), local.inferred_version))
  zone             = each.value.zone
  labels           = var.labels
  hostname         = each.value.hostname
  metadata         = each.value.metadata
  machine_type     = var.machine_type
  min_cpu_platform = var.min_cpu_platform

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

  boot_disk {
    device_name = "boot-disk"
    auto_delete = true
    initialize_params {
      image  = data.google_compute_image.bigip.self_link
      type   = var.disk_type
      size   = var.disk_size_gb
      labels = var.labels
    }
  }

  can_ip_forward = true
  tags = concat(
    [
      local.cluster_tag,
    ],
    try(length(var.network_tags), 0) != 0 ? var.network_tags : [],
  )

  dynamic "network_interface" {
    for_each = each.value.interfaces
    content {
      subnetwork = network_interface.value.subnet_id
      network_ip = network_interface.value.private_ip_primary != "unspecified" ? network_interface.value.private_ip_primary : null
      nic_type   = network_interface.value.nic_type
      dynamic "access_config" {
        for_each = network_interface.value.public_ip ? { public = true } : {}
        content {}
      }
      dynamic "alias_ip_range" {
        for_each = network_interface.value.private_ip_secondary
        content {
          ip_cidr_range         = alias_ip_range.value.cidr
          subnetwork_range_name = coalesce(alias_ip_range.value.range_name, "unspecified") != "unspecified" ? alias_ip_range.value.range_name : null
        }
      }
    }
  }

  lifecycle {
    # When deploying with CFE, Alias IP may be moved between instances on failover; ignore these changes and rely on
    # CFE doing the right thing. This will require a manual intervention if the Alias IPs are changed.
    ignore_changes = [
      network_interface[0].alias_ip_range,
      network_interface[1].alias_ip_range,
      network_interface[2].alias_ip_range,
      network_interface[3].alias_ip_range,
      network_interface[4].alias_ip_range,
      network_interface[5].alias_ip_range,
      network_interface[6].alias_ip_range,
      network_interface[7].alias_ip_range,
    ]
  }

  depends_on = [
    google_compute_address.dsc_control_plane,
    google_compute_address.dsc_data_plane,
  ]
}

# DSC requires BIG-IP instances to communicate via HTTPS management port on
# control-plane network.
resource "google_compute_firewall" "mgt_sync" {
  project     = data.google_compute_subnetwork.subnets[tostring(var.management_interface_index)].project
  name        = format("%s-allow-dsc-mgmt", var.prefix)
  network     = data.google_compute_subnetwork.subnets[tostring(var.management_interface_index)].network
  description = "BIG-IP ConfigSync support on management network"
  direction   = "INGRESS"
  source_tags = [random_id.cluster_tag.hex]
  target_tags = [random_id.cluster_tag.hex]
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
  project     = data.google_compute_subnetwork.subnets[tostring(local.dsc_data_plane_index)].project
  name        = format("%s-allow-dsc-data", var.prefix)
  network     = data.google_compute_subnetwork.subnets[tostring(local.dsc_data_plane_index)].network
  description = "BIG-IP ConfigSync support on data-plane network"
  direction   = "INGRESS"
  source_tags = [random_id.cluster_tag.hex]
  target_tags = [random_id.cluster_tag.hex]
  allow {
    protocol = "tcp"
    ports = [
      443,
      4353,
    ]
  }
  allow {
    protocol = "udp"
    ports = [
      1026,
    ]
  }
}
