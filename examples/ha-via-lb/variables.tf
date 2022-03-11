variable "prefix" {
  type        = string
  description = <<-EOD
The prefix to use when naming resources managed by this module. Must be RFC1035
compliant and between 1 and 58 characters in length, inclusive.
EOD
}

variable "project_id" {
  type        = string
  description = <<-EOD
The GCP project identifier where the BIG-IP HA pair will be created
EOD
}

variable "zones" {
  type        = list(string)
  description = <<-EOD
The compute zones where where the BIG-IP instances will be deployed. At least one
zone must be provided; if more than one zone is given, the instances will be
distributed among them.
EOD
}

variable "machine_type" {
  type        = string
  default     = "n1-standard-4"
  description = <<-EOD
The machine type to use for BIG-IP VMs; this may be a standard GCE machine type,
or a customised VM ('custom-VCPUS-MEM_IN_MB'). Default value is 'n1-standard-4'.
*Note:* machine_type is highly-correlated with network bandwidth and performance;
an N2 machine type will give better performance but has limited regional availability.
EOD
}

variable "image" {
  type = string
  validation {
    condition     = can(regex("^(?:https://www.googleapis.com/compute/v1/)?projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/global/images/[a-z][a-z0-9-]{0,61}[a-z0-9]", var.image))
    error_message = "The image variable must be a fully-qualified URI."
  }
  default     = "projects/f5-7626-networks-public/global/images/f5-bigip-16-1-1-0-0-16-payg-good-1gbps-210917181041"
  description = <<-EOD
The self-link URI for a BIG-IP image to use as a base for the VM cluster. This
can be an official F5 image from GCP Marketplace, or a customised image.
EOD
}

variable "mgmt_subnet_ids" {
  type = list(list(object({
    subnet_id          = string
    public_ip          = bool
    private_ip_primary = string
  })))
  validation {
    condition     = can(regex("^x*$", join("", flatten([for outer in var.mgmt_subnet_ids : [for entry in outer : (coalesce(entry.subnet_id, "unspecified") == "unspecified" || can(regex("^(?:https://www\\.googleapis\\.com/compute/v1/)?projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/regions/[a-z][a-z-]+[0-9]/subnetworks/[a-z]([a-z0-9-]{0,61}[a-z0-9])?$", entry.subnet_id))) && (coalesce(entry.private_ip_primary, "undefined") == "undefined" || can(regex("^(?:[0-9]{1,3}\\.){3}[0-9]{1,3}$", entry.private_ip_primary))) ? "x" : "!"]]))))
    error_message = "Each mgmt_subnet_ids entry must contain a fully-qualified subnet self-link, and a valid or empty private IPv4 address."
  }
  default = [
    [{ "subnet_id" = null, "public_ip" = null, "private_ip_primary" = null }],
    [{ "subnet_id" = null, "public_ip" = null, "private_ip_primary" = null }],
  ]
  description = <<EOD
TODO @memes - update
List of maps of subnetids of the virtual network where the virtual machines will reside.
EOD
}

variable "external_subnet_ids" {
  type = list(list(object({
    subnet_id            = string
    public_ip            = bool
    private_ip_primary   = string
    private_ip_secondary = string
  })))
  validation {
    condition     = can(regex("^x*$", join("", flatten([for outer in var.external_subnet_ids : [for entry in outer : (coalesce(entry.subnet_id, "unspecified") == "unspecified" || can(regex("^(?:https://www\\.googleapis\\.com/compute/v1/)?projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/regions/[a-z][a-z-]+[0-9]/subnetworks/[a-z]([a-z0-9-]{0,61}[a-z0-9])?$", entry.subnet_id))) && (coalesce(entry.private_ip_primary, "undefined") == "undefined" || can(regex("^(?:[0-9]{1,3}\\.){3}[0-9]{1,3}$", entry.private_ip_primary))) && (coalesce(entry.private_ip_secondary, "undefined") == "undefined" || can(regex("^(?:[0-9]{1,3}\\.){3}[0-9]{1,3}(?:/[0-9]{1,2})?$", entry.private_ip_secondary))) ? "x" : "!"]]))))
    error_message = "Each external_subnet_ids entry must contain a fully-qualified subnet self-link, and valid or empty private IPv4 addresses."
  }
  default = [
    [{ "subnet_id" = null, "public_ip" = null, "private_ip_primary" = null, "private_ip_secondary" = null }],
    [{ "subnet_id" = null, "public_ip" = null, "private_ip_primary" = null, "private_ip_secondary" = null }],
  ]
  description = <<-EOD
TODO @memes - update
EOD
}

variable "internal_subnet_ids" {
  type = list(list(object({
    subnet_id          = string
    public_ip          = bool
    private_ip_primary = string
  })))
  validation {
    condition     = can(regex("^x*$", join("", flatten([for outer in var.internal_subnet_ids : [for entry in outer : (coalesce(entry.subnet_id, "unspecified") == "unspecified" || can(regex("^(?:https://www\\.googleapis\\.com/compute/v1/)?projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/regions/[a-z][a-z-]+[0-9]/subnetworks/[a-z]([a-z0-9-]{0,61}[a-z0-9])?$", entry.subnet_id))) && (coalesce(entry.private_ip_primary, "undefined") == "undefined" || can(regex("^(?:[0-9]{1,3}\\.){3}[0-9]{1,3}$", entry.private_ip_primary))) ? "x" : "!"]]))))
    error_message = "Each internal_subnet_ids entry must contain a fully-qualified subnet self-link, and valid or empty private IPv4 addresses."
  }
  default = [
    [{ "subnet_id" = null, "public_ip" = null, "private_ip_primary" = null }],
    [{ "subnet_id" = null, "public_ip" = null, "private_ip_primary" = null }],
  ]
  description = <<-EOD
TODO @memes - update
EOD
}

variable "gcp_secret_name" {
  description = "The secret to get the secret version for"
  type        = string
  default     = ""
}

variable "labels" {
  type        = map(string)
  default     = {}
  description = <<EOD
An optional map of string key:value pairs that will be applied to all resources
created that accept labels. Default is an empty map.
EOD
}

variable "service_account" {
  type = string
  validation {
    condition     = can(regex("^(?:[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][a-z0-9-]{4,28}[a-z0-9]\\.iam|[0-9]+-compute@developer)\\.gserviceaccount\\.com$", var.service_account))
    error_message = "The service_account variable must be a valid GCP service account email address."
  }
  description = <<-EOD
The email address of the service account which will be used for BIG-IP instances.
EOD
}

variable "f5_ssh_publickey" {
  type        = string
  default     = "~/.ssh/id_rsa.pub"
  description = <<-EOD
The path to the SSH public key to install on BIG-IP instances for admin access.
EOD
}

variable "custom_user_data" {
  type        = string
  default     = null
  description = <<-EOD
Override the onboarding BASH script used by F5Networks/terraform-gcp-bigip-module.
EOD
}

variable "metadata" {
  description = "Provide custom metadata values for BIG-IP instance"
  type        = map(string)
  default     = {}
}

variable "sleep_time" {
  type        = string
  default     = "300s"
  description = "The number of seconds/minutes of delay to build into creation of BIG-IP VMs; default is 250. BIG-IP requires a few minutes to complete the onboarding process and this value can be used to delay the processing of dependent Terraform resources."
}

variable "targets" {
  type = object({
    groups    = bool
    instances = bool
  })
  default = {
    groups    = true
    instances = false
  }
  description = <<EOD
Defines the target types to create for integration with GCP forwarding-rules, and/or
load balancers.
EOD
}
