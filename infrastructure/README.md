# Litmus infrastructure K8s Operator

[![CharmHub Badge](https://charmhub.io/litmus-infrastructure-k8s/badge.svg)](https://charmhub.io/litmus-infrastructure-k8s)
[![Release](https://github.com/canonical/litmus-operators/actions/workflows/release.yaml/badge.svg)](https://github.com/canonical/litmus-operators/actions/workflows/release.yaml)
[![Discourse Status](https://img.shields.io/discourse/status?server=https%3A%2F%2Fdiscourse.charmhub.io&style=flat&label=CharmHub%20Discourse)](https://discourse.charmhub.io)

This directory contains the source code for a Charmed Litmus infrastructure K8s Operator that partially drives [LitmusChaos] on Kubernetes. It is designed to work together with other charms to deploy and operate the control plane of LitmusChaos, an open source platform for chaos testing.

## Usage

Assuming you have access to a bootstrapped Juju controller on Kubernetes, you can:

```bash
$ juju deploy litmus-infrastructure-k8s
```


## Contributing

Please see the [Juju SDK docs](https://juju.is/docs/sdk) for guidelines
on enhancements to this charm following best practice guidelines, and the
[contributing] doc for developer guidance.

[LitmusChaos]: https://litmuschaos.io/
[contributing]: https://github.com/canonical/litmus-operators/blob/main/CONTRIBUTING.md