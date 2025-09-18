# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

data "juju_model" "charmed-litmus" {
  name = var.model
}

module "auth" {
  source    = "git::https://github.com/canonical/litmus-operators//auth/terraform"
  model     = data.juju_model.charmed-litmus.name
  channel   = var.litmus_channel
  revision  = var.auth_revision
  resources = var.auth_resources
}

module "backend" {
  source    = "git::https://github.com/canonical/litmus-operators//backend/terraform"
  model     = data.juju_model.charmed-litmus.name
  channel   = var.litmus_channel
  revision  = var.backend_revision
  resources = var.backend_resources
}

module "chaoscenter" {
  source    = "git::https://github.com/canonical/litmus-operators//chaoscenter/terraform"
  model     = data.juju_model.charmed-litmus.name
  channel   = var.litmus_channel
  revision  = var.chaoscenter_revision
  resources = var.chaoscenter_resources
}

module "mongodb" {
  source     = "git::https://github.com/canonical/mongodb-k8s-operator//terraform"
  model      = data.juju_model.charmed-litmus.name
  channel    = var.mongodb_channel
  config     = var.mongodb_config
}

module "traefik" {
  source  = "git::https://github.com/canonical/traefik-k8s-operator//terraform"
  model   = data.juju_model.charmed-litmus.name
  channel = var.traefik_channel
  config  = var.traefik_config
}

# Juju integrations

resource "juju_integration" "auth-mongodb" {
  model = data.juju_model.charmed-litmus.name

  application {
    name     = module.auth.app_name
    endpoint = module.auth.endpoints.database
  }

  application {
    name     = module.mongodb.app_name
    endpoint = module.mongodb.database_endpoint
  }
}

resource "juju_integration" "backend-mongodb" {
  model = data.juju_model.charmed-litmus.name

  application {
    name     = module.backend.app_name
    endpoint = module.backend.endpoints.database
  }

  application {
    name     = module.mongodb.app_name
    endpoint = module.mongodb.database_endpoint
  }
}

resource "juju_integration" "backend-auth" {
  model = data.juju_model.charmed-litmus.name

  application {
    name     = module.backend.app_name
    endpoint = module.backend.endpoints.litmus-auth
  }

  application {
    name     = module.auth.app_name
    endpoint = module.auth.endpoints.litmus-auth
  }
}

resource "juju_integration" "chaoscenter-auth" {
  model = data.juju_model.charmed-litmus.name

  application {
    name     = module.chaoscenter.app_name
    endpoint = module.chaoscenter.endpoints.auth-http-api
  }

  application {
    name     = module.auth.app_name
    endpoint = module.auth.endpoints.http-api
  }
}

resource "juju_integration" "chaoscenter-backend" {
  model = data.juju_model.charmed-litmus.name

  application {
    name     = module.chaoscenter.app_name
    endpoint = module.chaoscenter.endpoints.backend-http-api
  }

  application {
    name     = module.backend.app_name
    endpoint = module.backend.endpoints.http-api
  }
}
