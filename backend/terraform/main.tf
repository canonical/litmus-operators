# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

resource "juju_application" "backend" {
  name  = var.app_name
  model = var.model

  charm {
    name     = "litmus-backend-k8s"
    channel  = var.channel
    revision = var.revision
    base     = var.base
  }

  constraints = var.constraints
  units       = var.units
  resources   = var.resources
  trust       = true
}
