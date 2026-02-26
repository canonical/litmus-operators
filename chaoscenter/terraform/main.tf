# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

resource "juju_application" "chaoscenter" {
  name       = var.app_name
  model_uuid = var.model_uuid

  charm {
    name     = "litmus-chaoscenter-k8s"
    channel  = var.channel
    revision = var.revision
    base     = var.base
  }

  constraints = var.constraints
  units       = var.units
  resources   = var.resources
  trust       = true
}
