#
# Module under test outputs
#
output "self_links" {
  value = module.test.self_links
}

output "target_groups" {
  value = module.test.target_groups
}

output "target_instances" {
  value = module.test.target_instances
}

output "names" {
  value = module.test.names
}

#
# Fixture outputs expected by Inspec
#
output "prefix" {
  value = local.prefix
}

output "project_id" {
  value = var.project_id
}

output "zones" {
  value = var.zones
}

output "bigip_sa" {
  value = var.bigip_sa
}

output "secret_key" {
  value = var.secret_key
}

output "bigip_user" {
  value = "bigipuser"
}

output "bigip_password" {
  sensitive = true
  value     = var.bigip_password
}

output "ssh_pubkey_file" {
  value = var.ssh_pubkey_file
}

output "labels" {
  value = var.labels
}

output "bigip_addresses" {
  value = [for k, v in module.test.mgmtPublicIPs : v]
}

output "bigip_address_0" {
  value = sort([for k, v in module.test.mgmtPublicIPs : v])[0]
}

output "bigip_address_1" {
  value = sort([for k, v in module.test.mgmtPublicIPs : v])[1]
}
