#
# Module under test outputs
#
output "instance_group_manager" {
  value = module.test.instance_group_manager
}

output "instance_group" {
  value = module.test.instance_group
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

output "labels" {
  value = var.labels
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

output "named_ports_json" {
  value = jsonencode(var.named_ports)
}
