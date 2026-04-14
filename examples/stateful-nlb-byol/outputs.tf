output "vip" {
  value       = google_compute_address.vip.address
  description = <<-EOD
    The public VIP for backend service.
    EOD
}

output "admin_password_secret_id" {
  value       = module.admin_password.secret_id
  description = <<-EOD
  EOD
}

output "self_links" {
  value = module.bigip_ha.self_links
}
