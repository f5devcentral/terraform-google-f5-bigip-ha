output "self_links" {
  value       = { for k, v in module.instances : v.name => v.self_link }
  description = <<-EOD
A map of BIG-IP instance name to fully-qualified self-links.
EOD
}

output "names" {
  value       = [for k, v in module.instances : v.name]
  description = <<-EOD
The instance names of the BIG-IPs.
EOD
}

output "mgmtPublicIPs" {
  value       = { for k, v in module.instances : v.name => v.mgmtPublicIP }
  description = <<-EOD
A map of BIG-IP instance name to public IP address, if any, on the management interface.
EOD
}

output "target_groups" {
  value       = [for k, v in google_compute_instance_group.group : v.self_link]
  description = <<-EOD
A list of fully-qualified BIG-IP unmanaged instance group self-links.
EOD
}

output "target_instances" {
  value       = [for k, v in google_compute_target_instance.target : v.self_link]
  description = <<-EOD
A list of fully-qualified target instance self-links for the BIG-IPs.
EOD
}
