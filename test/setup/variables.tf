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
  default     = ["0.0.0.0/0"]
  description = "CIDRs permitted to access BIG-IP admin. Default is '0.0.0.0/0'."
}
