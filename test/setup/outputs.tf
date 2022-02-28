output "harness_tfvars" {
  value       = abspath(local_file.harness_tfvars.filename)
  description = <<EOD
The name of the generated harness.tfvars file that will be a common input to all
test fixtures.
EOD
}

output "ssh_privkey_path" {
  value       = abspath(local_file.test_privkey.filename)
  description = <<EOD
The full path to the private SSH key that will be used to verify remote shell
access.
EOD
}
