# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

output "app_name" {
  description = "Name of the deployed application."
  value       = juju_application.backend.name
}

output "endpoints" {
  value = {
    # Requires
    database         = "database"
    litmus-auth      = "litmus-auth"
    tls-certificates = "tls-certificates"
    # Provides
    http-api = "http-api"
  }
}
