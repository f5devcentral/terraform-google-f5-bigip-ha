output "self_links" {
  value       = module.ha.self_links
  description = <<-EOD
A map of BIG-IP instance name to fully-qualified self-links.
EOD
}

output "names" {
  value       = module.ha.names
  description = <<-EOD
The instance names of the BIG-IPs.
EOD
}

output "mgmtPublicIPs" {
  value       = module.ha.mgmtPublicIPs
  description = <<-EOD
A map of BIG-IP instance name to public IP address, if any, on the management interface.
EOD
}

output "target_groups" {
  value       = module.ha.target_groups
  description = <<-EOD
A list of fully-qualified BIG-IP unmanaged instance group self-links.
EOD
}

output "target_instances" {
  value       = module.ha.target_instances
  description = <<-EOD
A list of fully-qualified target instance self-links for the BIG-IPs.
EOD
}
