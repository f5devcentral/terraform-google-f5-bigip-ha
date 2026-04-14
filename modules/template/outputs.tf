output "self_link" {
  value = google_compute_instance_template.bigip.self_link_unique
}

output "id" {
  value = google_compute_instance_template.bigip.id
}

output "name" {
  value = google_compute_instance_template.bigip.name
}
