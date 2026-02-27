# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

output "app_name" {
  description = "Name of the deployed application."
  value       = juju_application.infrastructure.name
}

# TODO: add outputs for the endpoints provided/required by this application once they are added to the charm
# output "endpoints" {
#   value = {
#     # Provides
#     litmus-infrastructure = "litmus-infrastructure"
#   }
# }
