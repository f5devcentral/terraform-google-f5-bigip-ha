variable "num_instances" {
  type    = number
  default = 2
  validation {
    # An HA group requires between 2 and 8 BIG-IP instances, inclusive.
    condition     = floor(var.num_instances) == var.num_instances && var.num_instances > 1 && var.num_instances < 9
    error_message = "The num_instances variable must be an integer between 2 and 8, inclusive."
  }
  description = <<-EOD
  The number of BIG-IP instances to create as an HA group. Default value is 2.
  EOD
}

variable "prefix" {
  type = string
  validation {
    # Instance template prefix is limited to 37 chars
    condition     = can(regex("^[a-z][a-z0-9-]{0,36}$", var.prefix))
    error_message = "The prefix variable must be RFC1035 compliant and between 1 and 37 characters in length."
  }
  description = <<-EOD
  The prefix to use when naming resources managed by this module. Must be RFC1035 compliant and between 1 and 37
  characters in length, inclusive.
  EOD
}

variable "description" {
  type        = string
  nullable    = true
  default     = null
  description = <<-EOD
  An optional description to add to the BIG-IP Instances created from the module. If null/empty (default), a description
  will be generated.
  EOD
}

variable "project_id" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "The project_id variable must must be 6 to 30 lowercase letters, digits, or hyphens; it must start with a letter and cannot end with a hyphen."
  }
  description = <<-EOD
  The GCP project identifier where the BIG-IP instances will be created.
  EOD
}

variable "zones" {
  type     = list(string)
  nullable = true
  default  = null
  validation {
    condition     = var.zones == null ? true : alltrue([for zone in var.zones : can(regex("^[a-z]{2,20}-[a-z]{4,20}[0-9]-[a-z]$", zone))])
    error_message = "Zones must be null or each zone must be a valid GCE zone name."
  }
  description = <<-EOD
  An optional list of Compute Engine Zone names where where the BIG-IP instances will be deployed; if null or empty
  (default), BIG-IP instances will be randomly distributed to known zones in the subnetwork region. If one or more zone
  is given, the BIG-IP instances will be constrained to the zones specified.
  EOD
}

variable "min_cpu_platform" {
  type        = string
  nullable    = true
  default     = null
  description = <<-EOD
An optional constraint used when scheduling the BIG-IP VMs; this value prevents
the VMs from being scheduled on hardware that doesn't meet the minimum CPU
micro-architecture. Default value is null.
EOD
}

variable "machine_type" {
  type        = string
  nullable    = false
  default     = "n1-standard-8"
  description = <<-EOD
The machine type to use for BIG-IP VMs; this may be a standard GCE machine type,
or a customised VM ('custom-VCPUS-MEM_IN_MB'). Default value is 'n1-standard-8'.
_NOTE:_ machine_type is highly-correlated with network bandwidth and performance;
an N2 machine type will give better performance but has limited regional availability.
EOD
}

variable "automatic_restart" {
  type        = bool
  nullable    = true
  default     = true
  description = <<-EOD
Determines if the BIG-IP VMs should be automatically restarted if terminated by
GCE. Defaults to true to match expected Google Compute Engine behaviour.
EOD
}

variable "preemptible" {
  type        = bool
  nullable    = true
  default     = false
  description = <<EOD
If set to true, the BIG-IP instances will be deployed on preemptible VMs, which
could be terminated at any time, and have a maximum lifetime of 24 hours. Default
value is false. DO NOT SET TO TRUE UNLESS YOU UNDERSTAND THE RAMIFICATIONS!
EOD
}

variable "image" {
  type     = string
  nullable = false
  validation {
    condition     = can(regex("^(?:https://www.googleapis.com/compute/v1/)?projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/global/images/[a-z][a-z0-9-]{0,61}[a-z0-9]", var.image))
    error_message = "The image variable must be a fully-qualified URI."
  }
  default     = "projects/f5-7626-networks-public/global/images/f5-bigip-21-0-0-1-0-0-13-payg-good-10gbps-260128095822"
  description = <<-EOD
The self-link URI for a BIG-IP image to use as a base for the VM cluster. This
can be an official F5 image from GCP Marketplace, or a customised image. The default value is the latest BIG-IP v21 PAYG
Good 10gbps image as of module publishing.
EOD
}

variable "disk_type" {
  type     = string
  nullable = false
  default  = "pd-ssd"
  validation {
    condition     = contains(["pd-balanced", "pd-ssd", "pd-standard"], var.disk_type)
    error_message = "The disk_type variable must be one of 'pd-balanced', 'pd-ssd', or 'pd-standard'."
  }
  description = <<EOD
The boot disk type to use with instances; can be 'pd-balanced', 'pd-ssd' (default),
or 'pd-standard'.
EOD
}

variable "disk_size_gb" {
  type        = number
  nullable    = true
  default     = null
  description = <<EOD
Use this flag to set the boot volume size in GB. If left at the default value
the boot disk will have the same size as the base image.
EOD
}

variable "interfaces" {
  # TODO(@memes) - Published BIG-IP images only support VIRTIO as of module publishing but this module will allow
  # changing this for testing purposes.
  type = list(object({
    subnet_id = string
    public_ip = optional(bool, null)
    nic_type  = optional(string, null)
  }))
  nullable = false
  validation {
    # There must be at least two interface declarations for a stateful BIG-IP cluster, and VMs support a max of 8 NICs
    condition = length(var.interfaces) > 1 && length(var.interfaces) < 9 && alltrue(
      [for interface in var.interfaces :
        # Each entry must have a subnet_id field that is a valid Compute Engine subnet name or self-link
        can(regex("^(?:https://www\\.googleapis\\.com/compute/v1/)?projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/regions/[a-z][a-z-]+[0-9]/subnetworks/[a-z]([a-z0-9-]{0,61}[a-z0-9])?$", interface.subnet_id)) &&
        interface.nic_type == null ? true : contains(["VIRTIO_NET", "GVNIC"], interface.nic_type)
      ]) && can(
      # All declared subnets must be in the same region
      one(
        distinct([for interface in var.interfaces : reverse(split("/", interface.subnet_id))[2]])
      )
      ) && length(
      # Each subnet id must be unique
      distinct([for interface in var.interfaces : regex("projects/[^/]+/regions/[^/]+/subnetworks/.*$", interface.subnet_id)])
    ) == length(var.interfaces)
    error_message = "Each interface value must contain a fully-qualified subnet self-link in the same Compute Engine region, and between 1 and 8 interfaces must be provided."
  }
  description = <<-EOD
  Defines the subnetworks that will be added to the BIG-IP VE instances, and an optional flag to assign a public IP
  address to the interface. The first entry will become attached to eth0, the second to eth1, etc. In a standard 2+ NIC
  deployment on GCP it is expected that the second entry will be used for BIG-IP management interface; if you want to
  change this use the variable `management_interface_index` to indicate the correct zero-based interface to use.
  EOD
}

variable "management_interface_index" {
  type     = number
  nullable = false
  validation {
    condition     = floor(var.management_interface_index) == var.management_interface_index && var.management_interface_index >= 0 && var.management_interface_index < 8
    error_message = "The management_interface_index must be an integer between 0 and 7 inclusive."
  }
  default     = 1
  description = <<-EOD
  Defines the zero-based index of the network interface that will be used exclusively for BIG-IP management interface on
  multi-nic deployments. The default value is 1, which will configure the BIG-IP during first boot to use eth1 for
  management interface and auto-configure it appropriately.
  EOD
}

variable "labels" {
  type     = map(string)
  nullable = true
  validation {
    # GCP resource labels must be lowercase alphanumeric, underscore or hyphen,
    # and the key must be <= 63 characters in length
    condition     = var.labels == null ? true : alltrue([for k, v in var.labels : can(regex("^[a-z][a-z0-9_-]{0,62}$", k)) && can(regex("^[a-z0-9_-]{0,63}$", v))])
    error_message = "Each label key:value pair must match expectations."
  }
  default     = null
  description = <<-EOD
  An optional map of string key:value pairs that will be applied to all resources created that accept labels, overriding
  the value present in the Instance Template. Default is null.
  EOD
}

variable "service_account" {
  type     = string
  nullable = false
  validation {
    condition     = var.service_account == null ? true : can(regex("^(?:[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][a-z0-9-]{4,28}[a-z0-9]\\.iam|[0-9]+-compute@developer)\\.gserviceaccount\\.com$", var.service_account))
    error_message = "The service_account variable must be a valid GCP service account email address."
  }
  description = <<-EOD
  The email address of the service account which will be used for BIG-IP instances.
  EOD
}

variable "metadata" {
  type     = map(string)
  nullable = true
  validation {
    # GCP metadata keys must be lowercase alphanumeric, underscore or hyphen,
    # and the key must be <= 128 characters in length, values must be <256Kb
    condition     = var.metadata == null ? true : alltrue([for k, v in var.metadata : can(regex("^[a-z0-9_-]{1,127}$", k))])
    error_message = "Each metadata key:value pair must match expectations."
  }
  default     = null
  description = <<-EOD
  An optional map of strings containing Compute Engine metadata values for BIG-IP instances that will be created from
  this module.
  EOD
}

variable "network_tags" {
  type     = list(string)
  nullable = true
  validation {
    # GCP tags must be RFC1035 compliant
    condition     = var.network_tags == null ? true : alltrue([for tag in var.network_tags : can(regex("^[a-z][a-z0-9_-]{0,62}$", tag))])
    error_message = "Each tag must be RFC1035 compliant expectations."
  }
  default     = null
  description = <<-EOD
  An optional set of network tags which will be added to the BIG-IP VMs, typically used to associate VMs with Cloud NAT
  and firewall rules.
  EOD
}

variable "cluster_network_tag" {
  type     = string
  nullable = true
  validation {
    # GCP tags must be RFC1035 compliant
    condition     = coalesce(var.cluster_network_tag, "unspecified") == "unspecified" ? true : can(regex("^[a-z][a-z0-9_-]{0,62}$", var.cluster_network_tag))
    error_message = "The cluster_network_tag must be RFC1035 compliant expectations."
  }
  default     = null
  description = <<-EOD
  The network tag which will be unique to this cluster of BIG-IP instances to enable sync-group Firewall rules, and can
  also be used in CFE declarations. If left blank (default), a random value will be generated.

  NOTE: The final set of tags applied to instances will be the union of `cluster_network_tag` and `network_tags`.
  EOD
}

variable "runtime_init_config" {
  type     = string
  nullable = false
  validation {
    condition     = can(jsondecode(var.runtime_init_config)) || can(yamldecode(var.runtime_init_config))
    error_message = "The runtime-init-config value must contain valid JSON or YAML declaration."
  }
  default     = <<-EOD
  controls:
      logLevel: info
  post_onboard_enabled:
    - name: save_config
      type: inline
      commands:
        - tmsh save sys config
  EOD
  description = <<-EOD
  A runtime-init JSON or YAML configuration that will be executed during initialisation. If omitted, the BIG-IP instances will
  be largely unconfigured, with only the management interface accessible.
  EOD
}

variable "runtime_init_installer" {
  type = object({
    url                          = optional(string, "https://cdn.f5.com/product/cloudsolutions/f5-bigip-runtime-init/v2.0.3/dist/f5-bigip-runtime-init-2.0.3-1.gz.run")
    sha256sum                    = optional(string, "e38fabfee268d6b965a7c801ead7a5708e5766e349cfa6a19dd3add52018549a")
    skip_telemetry               = optional(bool, false)
    skip_toolchain_metadata_sync = optional(bool, false)
    skip_verify                  = optional(bool, false)
    verify_gpg_key_url           = optional(string, null)
  })
  nullable    = true
  default     = {}
  description = <<-EOD
  Defines the location of the runtime-init package to install, and an optional SHA256 checksum. During initialisation,
  the runtime-init installer will be downloaded from this location - which can be an http/https/gs/file/ftp URL - and
  verified against the provided checksum, if provided. Additional flags can change the behaviour of runtime-init when used
  in restricted environments (see https://github.com/F5Networks/f5-bigip-runtime-init?tab=readme-ov-file#private-environments).
EOD
}

variable "host_domain" {
  type     = string
  nullable = true
  validation {
    condition     = coalesce(var.host_domain, "unspecified") == "unspecified" ? true : can(regex("^([a-z][a-z0-9-]{0,61}[a-z0-9]\\.){1,}[a-z][a-z0-9-]{0,61}[a-z0-9]$", var.host_domain))
    error_message = "Host_domain must be a valid DNS zone name."
  }
  default     = null
  description = <<-EOD
  Defines the common DNS domain name to append to each BIG-IP instance's name to set the Compute Engine hostname value.
  If null or empty (default), the Compute Engine hostname will not be specified and default Compute Engine hostname
  assignment will occur.
  NOTE: This can also be set or overridden on a per-instance basis using the `instances` variable.
  EOD
}

variable "instances" {
  type = map(object({
    hostname = optional(string)
    metadata = optional(map(string))
    interfaces = optional(list(object({
      primary_ip = optional(string)
      secondary_ips = optional(list(object({
        cidr       = string
        range_name = optional(string)
      })))
    })))
  }))
  nullable = true
  validation {
    condition = var.instances == null ? true : alltrue([for k, v in var.instances :
      # Validate the name of the instance (key)
      can(regex("^[a-z][a-z0-9-]{0,61}[a-z0-9]$", k)) &&
      # Each instance entry can be empty
      try(length(v), 0) == 0 ? true :
      # If not empty, the hostname entry must be a valid DNS name
      (coalesce(v.hostname, "unspecified") == "unspecified" ? true : can(regex("^([a-z][a-z0-9-]{0,61}[a-z0-9]\\.){1,}[a-z][a-z0-9-]{0,61}[a-z0-9]$", v.hostname))) &&
      # If not empty, each metadata key and value must be valid GCP entries; GCP restrictions are in terms of bytes so
      # this validation may pass invalid entries if key or value are using characters outside of ASCII
      (try(length(v.metadata), 0) == 0 ? true : alltrue([for key, value in v.metadata : (can(regex("^[a-zA-Z0-9-_]+$", key)) && length(key) < 128) && try(length(value), 0) <= 262144])) &&
      # If a list of interfaces are provided, validate each entry
      v.interfaces == null ? true : alltrue([for interface in v.interfaces :
        # Primary IP, if not null/empty, must be a valid IPv4 or IPv6 host address - NOT A CIDR
        interface.primary_ip == null ? true : can(cidrhost(format("%s/128", interface.primary_ip), 0)) || can(cidrhost(format("%s/32", interface.primary_ip), 0)) &&
        # If the list of secondary IPs is not null/empty, each entry must be a valid IPv4 or IPv6 CIDR with an
        # optional named secondary range.
        interface.secondary_ips == null ? true : alltrue([for secondary in interface.secondary_ips :
          can(cidrhost(secondary.cidr, 0)) && secondary.range_name == null ? true : can(regex("^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$", secondary.range_name))
        ])
      ])
    ])
    error_message = "Each interfaces entry key must be an RFC1035 compliant VM name, and valid or empty IP addresses for each entry."
  }
  default     = null
  description = <<-EOD
  An optional map of instances names that will be used to override num_instances and common parameters. When creating BIG-IP
  instances the names will correspond to the keys in `instances` variable, and each instance named will receive the
  hostname, primary and/or Alias IPs associated with the instance.
  EOD
}
