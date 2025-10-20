#
# Module under test outputs
#
output "self_links" {
  value = module.test.self_links
}

output "names" {
  value = module.test.names
}

output "instances_by_zone" {
  value = module.test.instances_by_zone
}

output "cluster_tag" {
  value = module.test.cluster_tag
}

#
# Fixture outputs expected by Inspec
#
output "prefix" {
  value = var.prefix
}

output "project_id" {
  value = var.project_id
}

output "service_account" {
  value = var.service_account
}

output "admin_username" {
  value = "admin"
}

output "admin_password" {
  value = var.admin_password
}

output "ssh_publickey" {
  value = var.ssh_publickey
}

output "labels" {
  value = var.labels
}

output "bigip_addresses" {
  value = [for k, v in module.test.public_mgmt_ips : v]
}

output "bigip_address_0" {
  value = sort([for k, v in module.test.public_mgmt_ips : v])[0]
}

output "bigip_address_1" {
  value = sort([for k, v in module.test.public_mgmt_ips : v])[1]
}

output "mgmt_interface_json" {
  value = jsonencode(var.mgmt_interface)
}

output "external_interface_json" {
  value = jsonencode(var.external_interface)
}

output "internal_interfaces_json" {
  value = jsonencode(var.internal_interfaces)
}

output "instances_json" {
  value = jsonencode(var.instances)
}
