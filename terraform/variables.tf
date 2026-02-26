# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

variable "model_uuid" {
  description = "Reference to an existing model resource or data source for the model to deploy to."
  type        = string
}

variable "litmus_channel" {
  description = "Charmhub channel to use when deploying Charmed Litmus charms."
  type        = string
  default     = "2/edge"
}

variable "auth_revision" {
  description = "Revision number of the Litmus Auth K8s charm"
  type        = number
  default     = null
}

variable "auth_resources" {
  description = "Resources to use with the application. Details about available options can be found at https://charmhub.io/litmus-auth-k8s/resources."
  type        = map(string)
  default     = {}
}

variable "backend_revision" {
  description = "Revision number of the Litmus Backend K8s charm"
  type        = number
  default     = null
}

variable "backend_resources" {
  description = "Resources to use with the application. Details about available options can be found at https://charmhub.io/litmus-backend-k8s/resources."
  type        = map(string)
  default     = {}
}

variable "chaoscenter_revision" {
  description = "Revision number of the Litmus Chaoscenter K8s charm"
  type        = number
  default     = null
}

variable "chaoscenter_resources" {
  description = "Resources to use with the application. Details about available options can be found at https://charmhub.io/litmus-chaoscenter-k8s/resources."
  type        = map(string)
  default     = {}
}

variable "mongodb_channel" {
  description = "The channel to use when deploying `mongodb-k8s` charm."
  type        = string
  default     = "6/stable"
}

variable "mongodb_config" {
  description = "Additional configuration for the MongoDB. Details about available options can be found at https://charmhub.io/mongodb-k8s/configurations?channel=6/stable."
  type        = map(string)
  default     = {}
}
