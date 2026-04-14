output "instance_group_manager" {
  value       = google_compute_region_instance_group_manager.mig.self_link
  description = <<-EOD
  The Compute Engine instance group manager self-link of the stateless BIG-IP VMs.
EOD
}

output "instance_group" {
  value       = google_compute_region_instance_group_manager.mig.instance_group
  description = <<-EOD
  The Compute Engine instance group self-link of the stateless BIG-IP VMs.
  EOD
}
