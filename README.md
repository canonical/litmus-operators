# litmus-operators

This repository is a monorepo hosting [Juju](https://juju.is/) Kubernetes charms that automate deploying and operating the control and execution planes of [LitmusChaos](https://github.com/litmuschaos/litmus), an open-source chaos engineering platform for Kubernetes.

The full user-facing documentation is available at [canonical-chaos-engineering.readthedocs-hosted.com](https://canonical-chaos-engineering.readthedocs-hosted.com/en/latest/).

## Architecture

The Charmed Litmus deployment consists of the following components, deployed as Juju applications on a Kubernetes cloud:

```
┌─────────────────────────────────────────────────────┐
│                   Control Plane                     │
│                                                     │
│  ┌─────────────┐  ┌──────────┐  ┌──────────────┐    │
│  │ ChaosCenter │──│ Auth     │──│ Backend      │    │
│  │ (frontend)  │  │ (gRPC +  │  │ (GraphQL API)│    │
│  │ port: 8185  │  │  HTTP)   │  │              │    │
│  └──────┬──────┘  └────┬─────┘  └──────┬───────┘    │
│         │              │               │            │
│         │         ┌────┴───────────────┴──┐         │
│         │         │     MongoDB           │         │
│         │         │     (shared DB)       │         │
│         │         └───────────────────────┘         │
│         │                                           │
│    Nginx reverse proxy routes:                      │
│      /auth/* → Auth HTTP API                        │
│      /api/*  → Backend GraphQL API                  │
│      /*      → ChaosCenter frontend                 │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│            Execution Plane (per namespace)          │
│                                                     │
│  ┌──────────────────┐     ┌─────────────────────┐   │
│  │ Infrastructure   │ ←── │ Target applications │   │
│  │ (beacon charm)   │     │ under test          │   │
│  └──────────────────┘     └─────────────────────┘   │
│         ↑ cross-model relation                      │
│         │                                           │
│    ChaosCenter provisions chaos infra here          │
└─────────────────────────────────────────────────────┘
```

### Charms

| Charm | Directory | Description |
|-------|-----------|-------------|
| `litmus-auth-k8s` | [`./auth`](./auth) | Authentication and authorization server. Manages users, projects, and authorizes requests. Exposes HTTP (ports 3000/3001) and gRPC (ports 3030/3031) endpoints. |
| `litmus-backend-k8s` | [`./backend`](./backend) | Backend API server. Serves GraphQL API for managing chaos workflows, experiments, and infrastructure. |
| `litmus-chaoscenter-k8s` | [`./chaoscenter`](./chaoscenter) | Web UI portal. Nginx reverse proxy routes to auth/backend services. Manages user accounts, environments, and infrastructure registration. |
| `litmus-infrastructure-k8s` | [`./infrastructure`](./infrastructure) | Workloadless beacon charm. When integrated with ChaosCenter via cross-model relation, signals it to provision namespace-scoped chaos infrastructure in the model where the beacon is deployed. |

### Shared library

The [`./libs`](./libs) directory contains `litmus-libs`, a shared Python package used by all charms. It provides:

- **Pydantic models**: `DatabaseConfig`, `TLSConfigData`
- **Interfaces**: `LitmusAuthProvider/Requirer`, `LitmusBackendApi`, `LitmusInfrastructure`, `SelfMonitoring`
- **Utilities**: `StatusManager`, `TlsReconciler`, hostname/version helpers

The library is published to PyPI as [`litmus-libs`](https://pypi.org/project/litmus-libs/) via tags starting with `libs-`.

### Key integrations

```
mongodb-k8s  ←──database──→  auth
mongodb-k8s  ←──database──→  backend
auth         ←──litmus-auth──→  backend       (gRPC endpoint exchange)
auth         ←──http-api──→  chaoscenter      (auth HTTP API)
backend      ←──http-api──→  chaoscenter      (backend HTTP API)
infrastructure ←──litmus-infrastructure──→ chaoscenter  (cross-model, optional)
```

Optional integrations: `tls-certificates`, `ingress` (Traefik), `charm-tracing` (Tempo), `logging` (Loki), `metrics-endpoint` (Prometheus).

### User management

ChaosCenter requires a Juju secret with two user credentials:

- **admin**: Human operator account with full ChaosCenter access
- **charm**: Bot account used by the charm for automated resource management

Passwords must meet Litmus policy: 8–16 characters, ≥1 digit, ≥1 lowercase, ≥1 uppercase, ≥1 special character from `@$!%*?_&#`.

```bash
SECRET_URI=$(juju add-secret cc-users "admin-password=MyAdmin1!" "charm-password=MyCharm1!")
juju grant-secret cc-users chaoscenter
juju config chaoscenter user_secrets="$SECRET_URI"
```

## Deploy

### Quick deploy (development)

```bash
# Create a model on a Kubernetes controller
juju add-model litmus

# Deploy charms
juju deploy litmus-auth-k8s auth --channel 2/edge --trust
juju deploy litmus-backend-k8s backend --channel 2/edge --trust
juju deploy litmus-chaoscenter-k8s chaoscenter --channel 2/edge --trust
juju deploy mongodb-k8s mongodb --trust

# Integrate
juju integrate auth:database mongodb
juju integrate backend:database mongodb
juju integrate auth:litmus-auth backend:litmus-auth
juju integrate auth:http-api chaoscenter:auth-http-api
juju integrate backend:http-api chaoscenter:backend-http-api

# Set up user credentials
SECRET_URI=$(juju add-secret cc-users "admin-password=Litmus123!" "charm-password=Charm123!")
juju grant-secret cc-users chaoscenter
juju config chaoscenter user_secrets="$SECRET_URI"
```

### Deploy with Terraform

See the [`./terraform`](./terraform) module, which orchestrates the full deployment including MongoDB and user secret creation. Example usage:

```hcl
module "charmed-litmus" {
  source         = "git::https://github.com/canonical/litmus-operators//terraform"
  model_uuid     = juju_model.litmus.uuid
  admin_password = "MyAdmin1!"
  charm_password = "MyCharm1!"
}
```

### Deploy with `jhack` (rapid local iteration)

The [`scripts/dev_deploy.sh`](./scripts/dev_deploy.sh) script uses `jhack` to deploy all charms from local source for development.

### Optional: TLS

Integrate all three control plane charms with a TLS certificates provider:

```bash
juju deploy self-signed-certificates
juju integrate auth:tls-certificates self-signed-certificates
juju integrate backend:tls-certificates self-signed-certificates
juju integrate chaoscenter:tls-certificates self-signed-certificates
```

### Optional: Ingress

Expose ChaosCenter externally via Traefik:

```bash
juju deploy traefik-k8s traefik --channel latest/stable --trust
juju integrate traefik chaoscenter:ingress
```

### Optional: Observability (COS)

Integrate with the [Canonical Observability Stack](https://charmhub.io/topics/canonical-observability-stack):

```bash
# Tracing (Tempo)
juju integrate tempo auth:charm-tracing
juju integrate tempo backend:charm-tracing
juju integrate tempo chaoscenter:charm-tracing
juju integrate tempo chaoscenter:workload-tracing

# Logging (Loki)
juju integrate loki auth:logging
juju integrate loki backend:logging
juju integrate loki chaoscenter:logging

# Metrics (Prometheus)
juju integrate prometheus chaoscenter:metrics-endpoint
```

### Enabling chaos infrastructure (execution plane)

Deploy the infrastructure beacon in a target model to enable chaos experiments
there. This uses cross-model relations:

```bash
# In the target model (where your apps under test live)
juju switch target-app
juju deploy litmus-infrastructure-k8s infrastructure --channel 2/edge --trust

# Offer the endpoint
juju offer infrastructure:litmus-infrastructure

# From the control plane model, consume the offer
juju switch litmus
juju integrate chaoscenter:litmus-infrastructure admin/target-app.infrastructure
```

Each Juju model maps to a Kubernetes namespace. The infrastructure beacon
provisions namespace-scoped chaos infrastructure, enabling experiments on
applications in that namespace.

## Project structure

```
litmus-operators/
├── auth/                    # litmus-auth-k8s charm
│   ├── src/charm.py         # Main charm code
│   ├── src/litmus_auth.py   # Workload control
│   ├── charmcraft.yaml      # Charm metadata and build config
│   ├── tox.ini              # Per-charm tox targets
│   └── tests/unit/          # Unit tests
├── backend/                 # litmus-backend-k8s charm
│   ├── src/charm.py
│   ├── src/litmus_backend.py
│   └── ...
├── chaoscenter/             # litmus-chaoscenter-k8s charm
│   ├── src/charm.py
│   ├── src/litmus_client.py     # Litmus HTTP API client
│   ├── src/user_manager.py      # User account management
│   ├── src/environment_manager.py
│   ├── src/infra_manager.py
│   ├── src/nginx_config.py      # Nginx reverse proxy config
│   ├── src/traefik_config.py    # Traefik ingress config
│   └── ...
├── infrastructure/          # litmus-infrastructure-k8s charm (workloadless)
│   ├── src/charm.py
│   └── ...
├── libs/                    # Shared litmus-libs Python package
│   ├── src/litmus_libs/
│   │   ├── interfaces/      # Relation interface implementations
│   │   ├── models.py        # Pydantic models (DatabaseConfig, TLSConfigData)
│   │   ├── status_manager.py
│   │   ├── tls_reconciler.py
│   │   └── utils.py
│   └── tests/unit/
├── terraform/               # Terraform deployment module
│   ├── main.tf              # Orchestrates all charms + integrations
│   ├── variables.tf         # Input variables
│   ├── outputs.tf           # Exported endpoints for external use
│   └── external/mongodb-k8s/  # MongoDB submodule
├── tests/
│   ├── integration/         # Integration tests (deploy real charms)
│   ├── unit/                # Cross-charm unit tests
│   └── terraform/           # Terraform module tests
├── scripts/
│   ├── dev_deploy.sh        # Quick local deploy via jhack
│   └── repack.sh            # Rebuild all charm packages
├── docs/adrs/               # Architecture Decision Records
├── tox.ini                  # Root tox orchestration
└── pyproject.toml           # Root project config (Python 3.12+)
```

