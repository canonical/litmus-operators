# Litmus Infrastructure K8s Terraform module

This folder contains a base [Terraform][Terraform] module for the litmus-infrastructure-k8s charm.

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
## Using litmus-infrastructure-k8s base module in higher level modules

If you want to use `litmus-infrastructure-k8s` base module as part of your Terraform module, import it
like shown below:

```text
data "juju_model" "my_model" {
  name_uuid = var.model_uuid
}

module "infrastructure" {
  source = "git::https://github.com/canonical/litmus-operators/infrastructure//terraform"
  
  model_uuid = juju_model.my_model.uuid
  (Customize configuration variables here if needed)
}
```


The complete list of available integrations can be found [here][infrastructure-integrations].

[Terraform]: https://www.terraform.io/
[Terraform Juju provider]: https://registry.terraform.io/providers/juju/juju/latest
[Juju]: https://juju.is
[infrastructure-integrations]: https://charmhub.io/litmus-infrastructure-k8s/integrations
