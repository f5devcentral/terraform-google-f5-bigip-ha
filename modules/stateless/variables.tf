variable "num_instances" {
  type    = number
  default = 2
  validation {
    # A stateless group should be created with zero or more instances.
    condition     = floor(var.num_instances) == var.num_instances && var.num_instances >= 0
    error_message = "The num_instances variable must be a positive integer >= 0."
  }
  description = <<-EOD
  The number of BIG-IP instances to create as a stateless group; if using with an autoscaler this value should be set to
  0. Default value is 2.
  EOD
}

variable "prefix" {
  type = string
  validation {
    # Instance template prefix is limited to 37 chars
    condition     = can(regex("^[a-z][a-z0-9-]{0,36}$", var.prefix))
    error_message = "The prefix variable must be RFC1035 compliant and between 1 and 37 characters in length '${var.prefix}'."
  }
  description = <<-EOD
  The prefix to use when naming resources managed by this module. Must be RFC1035 compliant and between 1 and 37
  characters in length, inclusive.
  EOD
}

variable "description" {
  type        = string
  nullable    = true
  default     = "Managed group of regional stateless BIG-IP instances"
  description = <<-EOD
  An optional description to add to the Regional Managed Instance Group created for stateless BIG-IP HA.
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
  (default) BIG-IP instances will be randomly distributed to known zones in the subnetwork region. If one or more zone
  is given, the instances will be constrained to the zones specified.
  EOD
}

variable "labels" {
  type     = map(string)
  nullable = true
  validation {
    # GCP resource labels must be lowercase alphanumeric, underscore or hyphen,
    # and the key must be <= 63 characters in length
    condition     = var.labels == null ? true : alltrue([for k, v in var.labels : can(regex("^[a-z][a-z0-9_-]{0,62}$", k)) && can(regex("^[a-z0-9_-]{0,63}$", v)) ? "x" : ""])
    error_message = "Each label key:value pair must match expectations."
  }
  default     = null
  description = <<EOD
  An optional map of string key:value pairs that will be applied to all resources created that accept labels, overriding
  the value present in the Instance Template. Default is null.
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
  An optional set of metadata values to add to all BIG-IP instances.
  NOTE: Setting this value will override the settings in the instance template, including the scripts to onboard the
  BIG-IPs.
  EOD
}

variable "instance_template" {
  type     = string
  nullable = false
  validation {
    condition     = can(regex("^(?:https://www\\.googleapis\\.com/compute/v1/)?projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/global/instanceTemplates/[a-z]([a-z0-9-]{0,61}[a-z0-9])?(?:\\?uniqueId=[0-9]+)$", var.instance_template))
    error_message = "The instance_template must be a valid Instance Template identifier or self-link."
  }
  description = <<-EOD
  The Compute Engine Instance Template self-link or qualified identifier that contains the common instance parameters to
  apply to all instances launched by this module.
  NOTE: If the module variables `labels`, and `metadata` are not empty they will be merged with the equivalent values
  contained in the Instance Template.
  EOD
}

variable "named_ports" {
  type     = map(number)
  nullable = true
  validation {
    condition     = var.named_ports == null ? true : alltrue([for name, port in var.named_ports : can(regex("^[a-z][a-z0-9-]{0,62}$", name)) && floor(port) == port && port > 0 && port < 65536])
    error_message = "Each named_ports entry must have a valid RFC1035 name as key, and an integer value between 1 and 65535 inclusive."
  }
  default     = null
  description = <<-EOD
  An optional map of names to port number that will become a set of named ports in the instance group.
  EOD
}

variable "health_check" {
  type = object({
    self_link         = optional(string)
    port              = optional(number, 26000)
    initial_delay_sec = optional(number, 600)
  })
  nullable = true
  validation {
    condition = var.health_check == null ? true : (
      coalesce(var.health_check.self_link, "unspecified") == "unspecified" ? true : can(regex("^(?:https://www\\.googleapis\\.com/compute/v1/)?projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/global/healthChecks/[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$", var.health_check.self_link))
      ) && (
      var.health_check.port == null ? true : floor(var.health_check.port) == var.health_check.port && var.health_check.port > 0 && var.health_check.port < 65536
      ) && (
      var.health_check.initial_delay_sec == null ? true : floor(var.health_check.initial_delay_sec) == var.health_check.initial_delay_sec && var.health_check.initial_delay_sec >= 0 && var.health_check.initial_delay_sec <= 3600
    )
    error_message = "The healthcheck variable should include an optional health check self-link, an optional integer port number for firewall, and an optional initial delay for onboarding."
  }
  default = {
    self_link         = null
    port              = 26000
    initial_delay_sec = 600
  }
  description = <<-EOD
  Provide an optional existing Google Cloud health check to use for instance health check (e.g. is the BIG-IP "alive"),
  and an optional TCP port that a health check will use. If the self-link value is null/empty (default) a simple HTTP
  health check will be created that attempts to connect to "/" on the TCP port specified. The default value for TCP port
  is 26000, and the default initial delay is 600s.
  NOTE: In most cases a GCP Firewall Rule is required to allow health check probes to reach the BIG-IP instances; this
  module will create a suitable rule unless port is explicitly set to null.
  EOD
}
