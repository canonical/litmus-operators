# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# Litmus Auth outputs required to interact with external components, i.e. TLS certificates providers

output "auth_app_name" {
  description = "Name of the deployed Litmus Auth application."
  value       = module.auth.app_name
}
output "auth_tls_certificates_endpoint" {
  description = "Name of the endpoint to integrate with TLS certificates provider."
  value       = module.auth.endpoints.tls-certificates
}

# Litmus Backend outputs required to interact with external components, i.e. TLS certificates providers

output "backend_app_name" {
  description = "Name of the deployed Litmus Backend application."
  value       = module.backend.app_name
}
output "backend_tls_certificates_endpoint" {
  description = "Name of the endpoint to integrate with TLS certificates provider."
  value       = module.backend.endpoints.tls-certificates
}

# Litmus ChaosCenter outputs required to interact with external components, i.e. TLS certificates providers

output "chaoscenter_app_name" {
  description = "Name of the deployed Litmus ChaosCenter application."
  value       = module.chaoscenter.app_name
}
output "chaoscenter_ingress_endpoint" {
  description = "Name of the endpoint to integrate with Ingress provider."
  value       = module.chaoscenter.endpoints.ingress
}
output "chaoscenter_tls_certificates_endpoint" {
  description = "Name of the endpoint to integrate with TLS certificates provider."
  value       = module.chaoscenter.endpoints.tls-certificates
}
