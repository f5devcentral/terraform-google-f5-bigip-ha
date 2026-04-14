variable "project_id" {
  type        = string
  description = <<-EOD
    The Google Cloud project identifier where the stateless BIG-IP HA cluster and supporting resources will be deployed.
    EOD
}

variable "name" {
  type     = string
  nullable = false
  validation {
    # Instance template prefix is limited to 37 chars to accommodate resource suffixes
    condition     = can(regex("^[a-z][a-z0-9-]{0,36}$", var.name))
    error_message = "The name variable must be RFC1035 compliant and between 1 and 37 characters in length."
  }
  description = <<-EOD
The name (and prefix) to use when naming resources managed by this module. Must be RFC1035
compliant and between 1 and 37 characters in length, inclusive.
EOD
}

variable "region" {
  type     = string
  nullable = false
  validation {
    condition     = can(regex("^[a-z]{2,}-[a-z]{2,}[0-9]$", var.region))
    error_message = "The region value must be a valid Google Cloud region name."
  }
  description = <<-EOD
  The Compute Engine regions in which to create the example application and VPCs. Default is `us-central1`.
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

variable "interfaces" {
  type = list(object({
    subnet_id = string
    public_ip = optional(bool, null)
    nic_type  = optional(string, null)
  }))
  nullable    = false
  description = <<-EOD
  Defines the subnetworks that will be added to the instance template, and an optional flag to assign a public IP
  address to the interface. The first entry will become attached to eth0, the second to eth1, etc. See module README for
  more details.
  EOD
}

variable "allowlist_cidrs" {
  type     = list(string)
  nullable = true
  validation {
    condition     = var.allowlist_cidrs == null ? true : alltrue([for cidr in var.allowlist_cidrs : can(cidrhost(cidr, 0))])
    error_message = "Each allowlist_cidrs entry mus be a valid IPv4 or IPv6 cidr."
  }
  default = [
    "0.0.0.0/0",
  ]
  description = <<-EOD
  An optional list of CIDRs to be permitted access to BIG-IP instances via public VIP. Default is ["0.0.0.0/0"].
  EOD
}
