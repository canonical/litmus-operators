# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
"""Generic self-monitoring integration wrappers for all litmus charms."""

from typing import Dict, Optional

import ops
import ops_tracing
from charms.loki_k8s.v1.loki_push_api import LogForwarder
from charms.tempo_coordinator_k8s.v0.tracing import TracingEndpointRequirer

_DEFAULT_ENDPOINT_MAPPING = {
    "charm-tracing": "charm-tracing",
    "logging": "logging",
}


class SelfMonitoring:
    """Self-monitoring relation integrator for all litmus charms.

    Automatically adds charm-tracing and pebble log forwarding (for all workload containers)
    integrations

    Usage:
    >>>    class MyCharm(CharmBase):
    >>>        def __init__(self, *a, **kw):
    >>>            super().__init__(*a, **kw)
    >>>            self._self_monitoring = SelfMonitoring(
    >>>                 self,
    >>>                 endpoint_overrides={
    >>>                     "charm-tracing": "send-charm-traces",
    >>>                 },
    >>>             )
    """

    _expected_interfaces = {
        "logging": "loki_push_api",
        "charm-tracing": "tracing",
    }

    def __init__(
        self,
        charm: ops.CharmBase,
        endpoint_overrides: Optional[Dict[str, str]] = None,
    ):
        endpoint_mapping = _DEFAULT_ENDPOINT_MAPPING.copy()
        if endpoint_overrides:
            endpoint_mapping.update(endpoint_overrides)

        self._validate_endpoints(charm, endpoint_mapping)

        # this injects a pebble-forwarding layer in all sidecars that this charm owns
        self._log_forwarder = LogForwarder(charm, relation_name=endpoint_mapping["logging"])
        # this sets up charm tracing with ops.tracing.
        self._charm_tracing = TracingEndpointRequirer(
            charm,
            relation_name=endpoint_mapping["charm-tracing"],
            protocols=["otlp_http"],
        )

    def _validate_endpoints(self, charm: ops.CharmBase, endpoint_mapping: Dict[str, str]):
        # verify that the charm's metadata has declared all endpoints we're being given here
        for internal_name, custom_name in endpoint_mapping.items():
            ep_meta = charm.meta.requires.get(custom_name, charm.meta.provides.get(custom_name))
            if ep_meta is None:
                # probably you passed an endpoint name to endpoint_mapping,
                # but forgot to add it to charmcraft.yaml or misspelled it
                raise ValueError(
                    f"Charm metadata is missing a required endpoint: {custom_name}({internal_name})"
                )

            if ep_meta.interface_name != self._expected_interfaces[internal_name]:
                raise ValueError(
                    f"Declared charm endpoint {custom_name}({internal_name}) has wrong interface name in metadata.yaml "
                    f"(expected {self._expected_interfaces[internal_name]}, got {ep_meta.interface_name})"
                )

    def reconcile(self, ca_cert: Optional[str]):
        """Unconditional logic related to self-monitoring to run regardless of the event we are processing."""
        if self._charm_tracing.is_ready():
            endpoint = self._charm_tracing.get_endpoint("otlp_http")
            if not endpoint:
                return
            ops_tracing.set_destination(
                url=endpoint + "/v1/traces",
                ca=ca_cert,
            )
