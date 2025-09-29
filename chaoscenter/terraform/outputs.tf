# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

output "app_name" {
  description = "Name of the deployed application."
  value       = juju_application.chaoscenter.name
}

output "endpoints" {
  value = {
    # Requires
    auth-http-api    = "auth-http-api"
    backend-http-api = "backend-http-api"
    tls-certificates = "tls-certificates"
    ingress          = "ingress"
    # Provides
    metrics-endpoint = "metrics-endpoint"
  }
}
