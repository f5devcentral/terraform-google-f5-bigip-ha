variable "num_instances" {
  type    = number
  default = 2
}

variable "prefix" {
  type = string
}

variable "project_id" {
  type = string
}

variable "zones" {
  type    = set(string)
  default = null
}

variable "min_cpu_platform" {
  type    = string
  default = "Intel Skylake"
}

variable "machine_type" {
  type = string
}

variable "automatic_restart" {
  type    = bool
  default = true
}

variable "preemptible" {
  type    = string
  default = false
}

variable "image" {
  type    = string
  default = "projects/f5-7626-networks-public/global/images/f5-bigip-17-1-1-3-0-0-5-payg-good-1gbps-240321070835"
}

variable "disk_type" {
  type    = string
  default = "pd-ssd"
}

variable "disk_size_gb" {
  type    = number
  default = 100
}

variable "mgmt_interface" {
  type = object({
    subnet_id = string
    public_ip = bool
  })
}

variable "external_interface" {
  type = object({
    subnet_id = string
    public_ip = bool
  })
}

variable "internal_interfaces" {
  type = list(object({
    subnet_id = string
    public_ip = bool
  }))
}

variable "labels" {
  type = map(string)
}

variable "service_account" {
  type = string
}

variable "ssh_publickey" {
  type = string
}

variable "metadata" {
  type    = map(string)
  default = {}
}

variable "network_tags" {
  type    = list(string)
  default = []
}

variable "admin_password" {
  type = string
}

variable "runtime_init_config" {
  type    = string
  default = null
}

variable "named_ports" {
  type    = map(number)
  default = {}
}
