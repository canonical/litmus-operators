# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

terraform {
  required_providers {
    juju = {
      source  = "juju/juju"
      version = ">= 0.14.0" # Using 0.14.0 to match MongoDB's strict version requirement
    }
  }
}
