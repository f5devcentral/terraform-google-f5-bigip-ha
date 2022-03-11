variable "prefix" {
  type = string
}

variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "zones" {
  type = set(string)
}

variable "bigip_sa" {
  type = string
}

variable "secret_key" {
  type = string
}

variable "bigip_password" {
  type = string
}

variable "ssh_pubkey_file" {
  type = string
}

variable "subnets" {
  type = list(string)
}

variable "labels" {
  type = map(string)
}

variable "sleep_time" {
  type = string
}

variable "test_prefix" {
  type = string
}

variable "public_mgmt" {
  type    = bool
  default = false
}

variable "public_external" {
  type    = bool
  default = false
}

variable "image" {
  type = string
}

variable "machine_type" {
  type = string
}

variable "num_nics" {
  type = number
}
