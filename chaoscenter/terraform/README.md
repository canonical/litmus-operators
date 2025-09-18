# Litmus Chaoscenter K8s Terraform module

This folder contains a base [Terraform][Terraform] module for the litmus-chaoscenter-k8s charm.

The module uses the [Terraform Juju provider][Terraform Juju provider] to model the charm
deployment onto any Kubernetes environment managed by [Juju][Juju].

The base module is not intended to be deployed in separation (it is possible though), but should
rather serve as a building block for higher level modules.

## Module structure

- **main.tf** - Defines the Juju application to be deployed.
- **variables.tf** - Allows customization of the deployment. Except for exposing the deployment
  options (Juju model name, channel or application name) also models the charm configuration.
- **output.tf** - Responsible for integrating the module with other Terraform modules, primarily
  by defining potential integration endpoints (charm integrations), but also by exposing
  the application name.
- **versions.tf** - Defines the Terraform provider version.
- 
## Using litmus-chaoscenter-k8s base module in higher level modules

If you want to use `litmus-chaoscenter-k8s` base module as part of your Terraform module, import it
like shown below:

```text
data "juju_model" "my_model" {
  name = var.model
}

module "chaoscenter" {
  source = "git::https://github.com/canonical/litmus-operators/chaoscenter//terraform"
  
  model = juju_model.my_model.name
  (Customize configuration variables here if needed)
}
```

Create integrations, for instance:

```text
resource "juju_integration" "chaoscenter-auth" {
  model = juju_model.my_model.name
  application {
    name     = module.chaoscenter.app_name
    endpoint = module.chaoscenter.endpoints.auth-http-api
  }
  application {
    name     = module.auth.app_name
    endpoint = module.auth.endpoints.litmus-auth
  }
}
```

The complete list of available integrations can be found [here][chaoscenter-integrations].

[Terraform]: https://www.terraform.io/
[Terraform Juju provider]: https://registry.terraform.io/providers/juju/juju/latest
[Juju]: https://juju.is
[chaoscenter-integrations]: https://charmhub.io/litmus-chaoscenter-k8s/integrations
