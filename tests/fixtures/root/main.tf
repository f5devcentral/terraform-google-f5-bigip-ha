terraform {
  required_version = ">= 0.14.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 3.85"
    }
  }
}

module "test" {
  source              = "./../../../"
  instances           = var.instances
  num_instances       = var.num_instances
  prefix              = var.prefix
  project_id          = var.project_id
  zones               = var.zones
  min_cpu_platform    = var.min_cpu_platform
  machine_type        = var.machine_type
  automatic_restart   = var.automatic_restart
  preemptible         = var.preemptible
  image               = var.image
  disk_type           = var.disk_type
  disk_size_gb        = var.disk_size_gb
  mgmt_interface      = var.mgmt_interface
  external_interface  = var.external_interface
  internal_interfaces = var.internal_interfaces
  labels              = var.labels
  service_account     = var.service_account
  metadata            = var.metadata
  network_tags        = var.network_tags
  # Override runtime-init installer defaults so that testing doesn't skew numbers
  runtime_init_installer = {
    url                          = "https://github.com/F5Networks/f5-bigip-runtime-init/releases/download/1.5.2/f5-bigip-runtime-init-1.5.2-1.gz.run"
    sha256sum                    = "b9eea6a7b2627343553f47d18f4ebbb2604cec38a6e761ce4b79d518ac24b2d4"
    skip_telemetry               = true
    skip_toolchain_metadata_sync = false
    skip_verify                  = false
    verify_gpg_key_url           = null
  }
  runtime_init_config = coalesce(var.runtime_init_config, templatefile(format("%s/templates/runtime-init-config.yaml", path.module), {
    admin_password = var.admin_password
    pubkey         = var.ssh_publickey
  }))
}
