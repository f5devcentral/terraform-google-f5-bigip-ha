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
The compute region where where the resources will be deployed.
EOD
}

variable "health_check_params" {
  type = object({
    check_interval_sec  = number
    timeout_sec         = number
    healthy_threshold   = number
    unhealthy_threshold = number
    port                = number
    request_path        = string
    response            = string
  })
  validation {
    condition     = (var.health_check_params.check_interval_sec == null || (var.health_check_params.check_interval_sec > 0 && floor(var.health_check_params.check_interval_sec) == var.health_check_params.check_interval_sec)) && (var.health_check_params.timeout_sec == null || (var.health_check_params.timeout_sec > 0 && floor(var.health_check_params.timeout_sec) == var.health_check_params.timeout_sec)) && (var.health_check_params.healthy_threshold == null || (var.health_check_params.healthy_threshold > 0 && floor(var.health_check_params.healthy_threshold) == var.health_check_params.healthy_threshold)) && (var.health_check_params.unhealthy_threshold == null || (var.health_check_params.unhealthy_threshold > 0 && floor(var.health_check_params.unhealthy_threshold) == var.health_check_params.unhealthy_threshold))
    error_message = "Each health_check_param member must be null, an integer > 0 (check_interval_sec, timeout_sec, healthy_threshold, unhealthy_threshold), an integer between 1 and 65535 (port)."
  }
  default = {
    check_interval_sec  = 5
    timeout_sec         = 2
    healthy_threshold   = 2
    unhealthy_threshold = 2
    port                = 40000
    request_path        = "/"
    response            = "OK"
  }
  description = <<-EOD
Set the Network load balancer health check parameters that will be used to direct
incoming traffic to a BIG-IP or NGINX instance for initial handling.
EOD
}

variable "address" {
  type = string
  validation {
    condition     = coalesce(var.address, "unspecified") == "unspecified" || can(regex("^(?:[0-9]{1,3}\\.){3}[0-9]{1,3}$", var.address))
    error_message = "The address must be a valid IPv4 address."
  }
  default     = null
  description = <<-EOD
The IPv4 address to use with the forwarding rule.
EOD
}

variable "protocols" {
  type = set(string)
  validation {
    condition     = var.protocols != null ? length(join("", [for protocol in var.protocols : can(regex("^(TCP|UDP|L3_DEFAULT)$", protocol)) ? "x" : ""])) == length(var.protocols) : true
    error_message = "The protocols variable must contain any/all of TCP and UDP."
  }
  default = [
    "TCP",
    "UDP"
  ]
  description = <<-EOD
The IP protocols that will be enabled for the internal load balacner.

Default value is ["TCP", "UDP"].
EOD
}

variable "instance_groups" {
  type = set(string)
  validation {
    condition     = length(var.instance_groups) > 0 && length(join("", [for group in var.instance_groups : can(regex("^(?:https://www.googleapis.com/compute/v1/)?projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/zones/[a-z]{2,20}-[a-z]{4,20}[0-9]-[a-z]/instanceGroups/[a-z][a-z0-9-]{0,61}[a-z0-9]$", group)) ? "x" : ""])) == length(var.instance_groups)
    error_message = "Each instance_group value must be a valid self-link or id."
  }
  description = <<-EOD
The set of instance groups that will become the backend services for the Network
load balancer.
EOD
}

variable "labels" {
  type        = map(string)
  default     = {}
  description = <<-EOD
An optional map of string key:value pairs to assign to created resources.
EOD
}

variable "target_service_account" {
  type = string
  validation {
    condition     = can(regex("^(?:[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][a-z0-9-]{4,28}[a-z0-9]\\.iam|[0-9]+-compute@developer)\\.gserviceaccount\\.com$", var.target_service_account))
    error_message = "The target_service_account variable must be a valid GCP service account email address."
  }
  description = <<-EOD
The email address of the service account which will be used for BIG-IP instances,
and used to apply ingress firewall rules for health checks.
EOD
}

variable "subnet" {
  type = string
  validation {
    condition     = can(regex("^https://www\\.googleapis\\.com/compute/v1/projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/regions/[a-z][a-z-]+[0-9]/subnetworks/[a-z]([a-z0-9-]{0,61}[a-z0-9])?$", var.subnet))
    error_message = "The subnet variable must be a fully-qualified self-link."
  }
  description = <<-EOD
The fully-qualified subnetwork self-link that the internal load balancer and
firewall rule will be applied to.
EOD
}

variable "global_access" {
  type        = bool
  default     = false
  description = <<-EOD
Boolean to enable global access to ILB; default is false.
EOD
}
