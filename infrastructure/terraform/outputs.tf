# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

output "app_name" {
  description = "Name of the deployed application."
  value       = juju_application.infrastructure.name
}

output "endpoints" {
  value = {
    # Provides
    litmus-infrastructure = "litmus-infrastructure"
  }
}
