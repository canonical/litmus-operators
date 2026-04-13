# litmus-libs
![PyPI](https://img.shields.io/pypi/v/litmus-libs)

Shared Python package used by all four Litmus charms. It provides:

- **Relation interfaces** — typed providers/requirers for the custom `litmus-auth`, `litmus-auth-http-api`, `litmus-backend-http-api`, and `litmus-infrastructure` Juju relations, plus self-monitoring bindings.
- **Typed data models** — Pydantic/dataclass wrappers for MongoDB credentials (`DatabaseConfig`) and TLS cert data (`TLSConfigData`), replacing raw dict passing.
- **StatusManager** — centralises `collect-status` logic (blocked on missing relations, waiting on missing config, blocked on failing Pebble checks).
- **TlsReconciler** — writes TLS cert/key/CA files into a workload container's filesystem and cleans them up when TLS is removed.
- **Utils** — small helpers like resolving the Kubernetes service FQDN for a Juju app.

# How to release
 
Go to https://github.com/canonical/litmus-operators/releases and click on 'Draft a new release'.

Select a tag from the dropdown, or create a new one from the `main` target branch. The tag needs to start with `libs-` to get picked up by pypi automation.

Enter a meaningful release title and in the description, put an itemized changelog listing new features and bugfixes, and whatever is good to mention.

Click on 'Publish release'.