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

output "instance_group_manager" {
  value       = module.bigip_ha.instance_group_manager
  description = <<-EOD
  The Compute Engine instance group manager self-link of the stateless BIG-IP VMs.
  EOD
}


output "instance_group" {
  value       = module.bigip_ha.instance_group
  description = <<-EOD
  The Compute Engine instance group self-link of the stateless BIG-IP VMs.
  EOD
}
