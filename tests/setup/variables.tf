# Common variables
variable "project_id" {
  type        = string
  description = "GCP project id."
}

variable "region" {
  type        = string
  description = "Compute engine region where resources will be created."
}

variable "labels" {
  type        = map(string)
  default     = {}
  description = "Optional additional labels to apply to resources."
}

variable "admin_source_cidrs" {
  type        = list(string)
  default     = []
  description = "CIDRs permitted to access BIG-IP admin. An empty/null set will use an autodetected CIDR of host."
}
