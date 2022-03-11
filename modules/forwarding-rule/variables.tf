variable "project_id" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "The project_id variable must must be 6 to 30 lowercase letters, digits, or hyphens; it must start with a letter and cannot end with a hyphen."
  }
  description = <<-EOD
The GCP project identifier where the BIG-IP cluster will be created
EOD
}

variable "prefix" {
  type = string
  validation {
    # This module adds "-XXX" suffix to each forwarding-rule name, where -XXX is
    # one of '-tcp', '-udp', or '-l3-default', so validate that the prefix is RFC1035
    # compliant with a maximum length of 52 chars.
    condition     = can(regex("^[a-z][a-z0-9-]{0,51}$", var.prefix))
    error_message = "The prefix variable must be RFC1035 compliant and between 1 and 52 characters in length."
  }
  description = <<-EOD
The prefix to use when naming resources managed by this module. Must be RFC1035
compliant and between 1 and 52 characters in length, inclusive.
EOD
}

variable "region" {
  type = string
  validation {
    condition     = can(regex("^[a-z]{2,20}-[a-z]{4,20}[0-9]$", var.region))
    error_message = "The region variable must be a valid GCE region name."
  }
  description = <<-EOD
The compute region where where the forwarding-rules will be deployed.
EOD
}

variable "is_external" {
  type        = bool
  default     = true
  description = <<-EOD
A boolean flag to determine if the forwarding-rule will be for ingress from external
internet (default), or it it will be forwarding internal only traffic.
EOD
}

variable "address" {
  type = string
  validation {
    condition     = can(regex("^(?:[0-9]{1,3}\\.){3}[0-9]{1,3}$", var.address))
    error_message = "The address must be a valid IPv4 address."
  }
  description = <<-EOD
The IPv4 address to use with the forwarding rule.
EOD
}

variable "protocols" {
  type = set(string)
  validation {
    condition     = var.protocols != null ? length(join("", [for protocol in var.protocols : can(regex("^(TCP|UDP|L3_DEFAULT)$", protocol)) ? "x" : ""])) == length(var.protocols) : true
    error_message = "The protocols variable must contain any/all of TCP, UDP, or L3_DEFAULT."
  }
  default = [
    "TCP",
    "UDP"
  ]
  description = <<-EOD
The IP protocols that will be enabled in the forwarding rule(s); a rule will be
created for each protocol specified. NOTE: L3_DEFAULT is only valid for an external
forwarding-rule instance (i.e. when is_external = true).

Default value is ["TCP", "UDP"].
EOD
}

variable "targets" {
  type = set(string)
  validation {
    condition     = length(join("", [for target in var.targets : can(regex("^(?:https://www.googleapis.com/compute/v1/)?projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/zones/[a-z]{2,20}-[a-z]{4,20}[0-9]-[a-z]/targetInstances/[a-z][a-z0-9-]{0,61}[a-z0-9]$", target)) ? "x" : ""])) == length(var.targets)
    error_message = "Each target must be a valid self-link or name."
  }
  description = <<-EOD
The VM target instance self-links for the forwarding-rule(s).
EOD
}

variable "labels" {
  type        = map(string)
  default     = {}
  description = <<-EOD
An optional map of string key:value pairs to assign to created resources.
EOD
}

variable "subnet" {
  type = string
  validation {
    condition     = var.subnet != null ? can(regex("^https://www\\.googleapis\\.com/compute/v1/projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/regions/[a-z][a-z-]+[0-9]/subnetworks/[a-z]([a-z0-9-]{0,61}[a-z0-9])?$", var.subnet)) : true
    error_message = "The subnet variable must be a fully-qualified self-link."
  }
  default     = null
  description = <<-EOD
The fully-qualified subnetwork self-link to which the forwarding rule will be
attached. Required if `is_external` is false; Terraform apply will fail if
subnet is null/empty and an internal forwarding rule is requested.
EOD
}
