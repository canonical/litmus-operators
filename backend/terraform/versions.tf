# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

terraform {
  required_providers {
    juju = {
      source  = "juju/juju"
      version = ">= 0.14.0" # We can't go higher than 0.14.0 if we want to use official MongoDB TF module
    }
  }
}
