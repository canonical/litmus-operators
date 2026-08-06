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
  uuid = var.model_uuid
}

module "chaoscenter" {
  source = "git::https://github.com/canonical/litmus-operators/chaoscenter//terraform"
  
  model_uuid = juju_model.my_model.uuid
  (Customize configuration variables here if needed)
}
```

Create integrations, for instance:

```text
resource "juju_integration" "chaoscenter-auth" {
  model_uuid = juju_model.my_model.uuid
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

<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
| ---- | ------- |
| <a name="requirement_juju"></a> [juju](#requirement\_juju) | >= 1.0 |

## Providers

| Name | Version |
| ---- | ------- |
| <a name="provider_juju"></a> [juju](#provider\_juju) | >= 1.0 |

## Modules

No modules.

## Inputs

| Name | Description | Type | Default | Required |
| ---- | ----------- | ---- | ------- | :------: |
| <a name="input_app_name"></a> [app\_name](#input\_app\_name) | Name of the application in the Juju model. | `string` | `"litmus-chaoscenter"` | no |
| <a name="input_base"></a> [base](#input\_base) | The operating system on which to deploy | `string` | `"ubuntu@24.04"` | no |
| <a name="input_channel"></a> [channel](#input\_channel) | Charmhub channel to use when deploying a charm. | `string` | `"2/edge"` | no |
| <a name="input_config"></a> [config](#input\_config) | Map of the charm configuration options | `map(string)` | `{}` | no |
| <a name="input_constraints"></a> [constraints](#input\_constraints) | Juju constraints to apply for this application. | `string` | `"arch=amd64"` | no |
| <a name="input_model_uuid"></a> [model\_uuid](#input\_model\_uuid) | Reference to an existing model resource or data source for the model to deploy to. | `string` | n/a | yes |
| <a name="input_resources"></a> [resources](#input\_resources) | Resources to use with the application. Details about available options can be found at https://charmhub.io/litmus-chaoscenter-k8s/resources. | `map(string)` | `{}` | no |
| <a name="input_revision"></a> [revision](#input\_revision) | Revision number of the charm | `number` | `null` | no |
| <a name="input_units"></a> [units](#input\_units) | Number of units to deploy | `number` | `1` | no |

## Outputs

| Name | Description |
| ---- | ----------- |
| <a name="output_app_name"></a> [app\_name](#output\_app\_name) | Name of the deployed application. |
| <a name="output_endpoints"></a> [endpoints](#output\_endpoints) | n/a |
<!-- END_TF_DOCS -->