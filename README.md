# litmus-operators

This repository is a monorepo hosting [Juju](https://juju.is/) Kubernetes charms that automate deploying and operating the control and execution planes of [LitmusChaos](https://litmuschaos.io/), an open-source chaos engineering platform for Kubernetes.

The full user-facing documentation is available at [canonical-chaos-engineering.readthedocs-hosted.com](https://canonical-chaos-engineering.readthedocs-hosted.com/en/latest/).


### Charms

| Charm | Readme | Description |
|-------|-----------|-------------|
| `litmus-chaoscenter-k8s` | [`./chaoscenter`](./chaoscenter/README.md) | Main web UI portal for the control plane. |
| `litmus-auth-k8s` | [`./auth`](./auth/README.md) | Authentication and authorization server. Manages users, projects, and authorizes requests. |
| `litmus-backend-k8s` | [`./backend`](./backend/README.md) | Backend API server. Serves a GraphQL API for managing chaos workflows, experiments, and infrastructure. |
| `litmus-infrastructure-k8s` | [`./infrastructure`](./infrastructure/README.md) | Represents a chaos infrastructure in the Juju model it's deployed in. |

### Shared library

The [`./libs`](./libs) directory contains `litmus-libs`, a shared Python package used by all charms. It provides:

- **Pydantic models**: `DatabaseConfig`, `TLSConfigData`
- **Interfaces**: `LitmusAuthProvider/Requirer`, `LitmusBackendApi`, `LitmusInfrastructure`, `SelfMonitoring`
- **Utilities**: `StatusManager`, `TlsReconciler`, hostname/version helpers

The library is published to PyPI as [`litmus-libs`](https://pypi.org/project/litmus-libs/) via tags starting with `libs-`.


## Deploy

### Deploy with Terraform

See the [`./terraform`](./terraform) module, which orchestrates the full deployment including MongoDB and user secret creation. Example usage:

```hcl
module "charmed-litmus" {
  source         = "git::https://github.com/canonical/litmus-operators//terraform"
  model_uuid     = juju_model.litmus.uuid
  admin_password = "Admin1!pass"
  charm_password = "Charm1!pass"
}
```

