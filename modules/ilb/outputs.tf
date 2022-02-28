output "addresses" {
  value       = distinct([for k, v in google_compute_forwarding_rule.ilb : v.ip_address])
  description = <<-EOD
A list of unique forwarding-rule IPv4 addresses.
EOD
}

output "protocol_addresses" {
  value       = { for k, v in google_compute_forwarding_rule.ilb : k => v.ip_address }
  description = <<-EOD
A map of protocols to Network load balancer IPv4 address.
EOD
}

output "self_links" {
  value       = { for k, v in google_compute_forwarding_rule.ilb : k => v.self_link }
  description = <<-EOD
A map of  protocols to fully-qualified Network load balancer self-links.
EOD
}
