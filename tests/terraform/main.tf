# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

module "litmus" {
  source         = "../../terraform"
  model          = var.model
  litmus_channel = var.channel
}
