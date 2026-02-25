# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

variable "app_name" {
  description = "Name of the application in the Juju model."
  type        = string
  default     = "litmus-chaoscenter"
}

variable "channel" {
  description = "Charmhub channel to use when deploying a charm."
  type        = string
  default     = "2/edge"
}

variable "constraints" {
  description = "Juju constraints to apply for this application."
  type        = string
  default     = "arch=amd64"
}

variable "model_uuid" {
  description = "Reference to an existing model resource or data source for the model to deploy to."
  type        = string
}

variable "resources" {
  description = "Resources to use with the application. Details about available options can be found at https://charmhub.io/litmus-chaoscenter-k8s/resources."
  type        = map(string)
  default     = {}
}

variable "revision" {
  description = "Revision number of the charm"
  type        = number
  default     = null
}

variable "base" {
  description = "The operating system on which to deploy"
  type        = string
  default     = "ubuntu@24.04"
}

variable "units" {
  description = "Number of units to deploy"
  type        = number
  default     = 1
}
