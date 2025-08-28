# Contributing

## Overview

This documents explains the processes and practices recommended for contributing enhancements to the charms in this repository.

- Generally, before developing enhancements to any of these charms, you should consider [opening an issue
  ](https://github.com/canonical/litmus-operators/issues) explaining your use case.
- If you would like to chat with us about your use-cases or proposed implementation, you can reach
  us at the [Canonical Observability Matrix public channel](https://matrix.to/#/#cos:ubuntu.com)
  or [Discourse](https://discourse.charmhub.io/).
- Familiarising yourself with the [Charmed Operator Framework](https://juju.is/docs/sdk) library
  will help you a lot when working on new features or bug fixes.
- All enhancements require review before being merged. Code review typically examines
  - code quality
  - test coverage
  - user experience for Juju administrators using the charm.
- Please help us out in ensuring easy to review branches by rebasing your pull request branch onto
  the `main` branch. This also avoids merge commits and creates a linear Git commit history.

## Developing

You can use the environments created by `tox` for development:

```shell
tox --notest -e unit
source .tox/unit/bin/activate
```

### Container images

We are using the following images built by [oci-factory](https://github.com/canonical/oci-factory):
- `ubuntu/litmuschaos-authserver`
  - [source](https://github.com/canonical/litmuschaos-authserver-rock)
  - [dockerhub](https://hub.docker.com/r/ubuntu/litmuschaos-authserver)


### Testing

```shell
tox -e fmt           # update your code according to formatting rules
tox -e lint          # lint the codebase
tox -e unit          # run the unit testing suite
tox -e integration   # run the integration testing suite
tox -e sync_libs     # sync the library with all components
tox                  # runs 'lint' and 'unit' environments
```

## Build charm

Build the charm in this git repository using:

```shell
cd ./auth; charmcraft pack
```

This will create:
- `auth/litmus-auth-k8s_ubuntu@24.04-amd64.charm`

### Deploy

```bash
# Create a model
juju add-model dev
# Enable DEBUG logging
juju model-config logging-config="<root>=INFO;unit=DEBUG"
# Deploy the charm
juju deploy ./auth/litmus-auth-k8s_ubuntu@24.04-amd64.charm \
    --resource litmus-auth-image=litmuschaos/litmusportal-auth-server:3.19.0 \
    --trust litmus-auth
```
