# Charmed Litmus Terraform Module

This folder contains the [Terraform][Terraform] module to deploy Charmed Litmus solution.

The module uses the [Terraform Juju provider][Terraform Juju provider] to model the charm deployment onto any Kubernetes environment managed by [Juju][Juju].

## Module structure

- **main.tf** - Defines the Juju application to be deployed.
- **variables.tf** - Allows customization of the deployment including Juju model name, charm's channel and configuration.
- **output.tf** - Responsible for integrating the module with other Terraform modules, primarily by defining potential integration endpoints (charm integrations).
- **versions.tf** - Defines the Terraform provider.

## Deploying Charmed Litmus with Terraform

### Pre-requisites

The following tools need to be installed and should be running in the environment.

- A Kubernetes cluster
- Juju controller bootstrapped onto the K8s cluster
- Terraform

### Deployment

Initialize the provider:

```console
terraform init
```

Create the `terraform.tfvars` file to specify the name of the Juju model to deploy to. The model should already exist.

```console
cat << EOF | tee terraform.tfvars
model = "my_model_name"

# Customize the configuration variables here if needed
EOF
```

Deploy the resources:

```console
terraform apply -var-file="terraform.tfvars" -auto-approve 
```

### Checking the result

Run `juju switch <juju model>` to switch to the target Juju model and observe the status of the applications.

```console
juju status --relations
```

This will show an output similar to the following:

```console
Model              Controller                  Cloud/Region                Version  SLA          Timestamp
charmed-litmus-tf  microk8s-classic-localhost  microk8s-classic/localhost  3.6.9    unsupported  12:25:15+02:00

App                 Version  Status  Scale  Charm                   Channel   Rev  Address         Exposed  Message
litmus-auth                  active      1  litmus-auth-k8s         2/edge      3  10.152.183.92   no       
litmus-backend               active      1  litmus-backend-k8s      2/edge      4  10.152.183.186  no       
litmus-chaoscenter           active      1  litmus-chaoscenter-k8s  2/edge      7  10.152.183.102  no       Ready at http://litmus-chaoscenter.charmed-litmus-tf.svc.cluster.local:8185.
mongodb-k8s         6.0.24   active      3  mongodb-k8s             6/stable   81  10.152.183.175  no       

Unit                   Workload  Agent  Address       Ports  Message
litmus-auth/0*         active    idle   10.1.194.219         
litmus-backend/0*      active    idle   10.1.194.231         
litmus-chaoscenter/0*  active    idle   10.1.194.255         Ready at http://litmus-chaoscenter.charmed-litmus-tf.svc.cluster.local:8185.
mongodb-k8s/0*         active    idle   10.1.194.214         
mongodb-k8s/1          active    idle   10.1.194.198         
mongodb-k8s/2          active    idle   10.1.194.230         

Integration provider           Requirer                             Interface                Type     Message
litmus-auth:http-api           litmus-chaoscenter:auth-http-api     litmus_auth_http_api     regular  
litmus-auth:litmus-auth        litmus-backend:litmus-auth           litmus_auth              regular  
litmus-backend:http-api        litmus-chaoscenter:backend-http-api  litmus_backend_http_api  regular  
mongodb-k8s:database           litmus-auth:database                 mongodb_client           regular  
mongodb-k8s:database           litmus-backend:database              mongodb_client           regular  
mongodb-k8s:database-peers     mongodb-k8s:database-peers           mongodb-peers            peer     
mongodb-k8s:ldap-peers         mongodb-k8s:ldap-peers               ldap-peers               peer     
mongodb-k8s:status-peers       mongodb-k8s:status-peers             status-peers             peer     
mongodb-k8s:upgrade-version-a  mongodb-k8s:upgrade-version-a        upgrade                  peer
```

### Cleaning up

Destroy the deployment:

```console
terraform destroy -auto-approve
```

[Terraform]: https://www.terraform.io/
[Terraform Juju provider]: https://registry.terraform.io/providers/juju/juju/latest
[Juju]: https://juju.is
