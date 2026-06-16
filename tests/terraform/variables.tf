# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

variable "model_uuid" {
  description = "Reference to an existing model resource or data source for the model to deploy to."
  type        = string
}

variable "channel" {
  description = "Charm channel to deploy"
  type        = string
}

variable "admin_password" {
  description = "The password to set for the Litmus admin user."
  type        = string
  sensitive   = true
}

variable "charm_password" {
  description = "The password to set for the Litmus charm bot user."
  type        = string
  sensitive   = true
}