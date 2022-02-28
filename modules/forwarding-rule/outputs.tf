output "addresses" {
  value       = distinct([for k, v in google_compute_forwarding_rule.fwd : v.ip_address])
  description = <<-EOD
A list of unique forwarding-rule IPv4 and/or IPv6 addresses.
EOD
}

output "protocol_addresses" {
  value       = { for k, v in google_compute_forwarding_rule.fwd : k => v.ip_address }
  description = <<-EOD
A map of protocols to forwarding-rule IPv4 and/or IPv6 address.
EOD
}

output "self_links" {
  value       = { for k, v in google_compute_forwarding_rule.fwd : k => v.self_link }
  description = <<-EOD
A map of  protocols to fully-qualified forwarding-rule self-links.
EOD
}

output "names" {
  value       = [for k, v in google_compute_forwarding_rule.fwd : v.name]
  description = <<-EOD
A list of forwarding-rule names.
EOD
}
