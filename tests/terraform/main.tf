# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

module "litmus" {
  source         = "../../terraform"
  model_uuid     = var.model_uuid
  litmus_channel = var.channel
  admin_password = var.admin_password
  charm_password = var.charm_password
}
