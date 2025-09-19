# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

output "auth_app_name" {
  description = "Name of the deployed Litmus Auth application."
  value       = module.auth.app_name
}

output "backend_app_name" {
  description = "Name of the deployed Litmus Backend application."
  value       = module.backend.app_name
}

output "chaoscenter_app_name" {
  description = "Name of the deployed Litmus ChaosCenter application."
  value       = module.chaoscenter.app_name
}
