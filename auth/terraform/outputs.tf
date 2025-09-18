# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

output "app_name" {
  description = "Name of the deployed application."
  value       = juju_application.auth.name
}

output "endpoints" {
  value = {
    # Requires
    database         = "database"
    tls-certificates = "tls-certificates"
    # Provides
    litmus-auth = "litmus-auth"
    http-api    = "http-api"
  }
}
