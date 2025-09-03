from collections import namedtuple
from typing import Any, Dict, List, Optional, Tuple

import ops
from charms.grafana_k8s.v0.grafana_dashboard import GrafanaDashboardProvider
from charms.loki_k8s.v1.loki_push_api import LogForwarder
from charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider
from charms.tempo_coordinator_k8s.v0.tracing import ReceiverProtocol, TracingEndpointRequirer

_Endpoint = namedtuple("_Endpoint", "name, interface")


class SelfMonitoring:
    """Self-monitoring relation integrator for all litmus charms."""

    _endpoint_mapping = {
        "charm-tracing": _Endpoint("charm-tracing", "tracing"),
        "workload-tracing": _Endpoint("workload-tracing", "tracing"),
        "logging": _Endpoint("logging", "loki_push_api"),
        "prometheus-scrape": _Endpoint("prometheus-scrape", "prometheus_scrape"),
        "grafana-dashboard": _Endpoint("grafana-dashboard", "grafana_dashboard"),
        # FIXME: update with https://github.com/canonical/litmus-operators/issues/39
        # "tls-certificates": _Endpoint("tls-certificates", "tls_certificates"),
    }

    def __init__(
        self,
        charm: ops.CharmBase,
        workload_tracing_protocols: Optional[List[ReceiverProtocol]] = None,
        prometheus_scrape_jobs: Optional[List[Dict[str, Any]]] = None,
    ):
        self._validate_endpoints(charm)

        # this injects a pebble-forwarding layer in all sidecars that this charm owns
        self._log_forwarder = LogForwarder(
            charm, relation_name=self._endpoint_mapping["logging"].name
        )

        self._charm_tracing = ops.tracing.Tracing(
            charm,
            tracing_relation_name=self._endpoint_mapping["charm-tracing"].name,
            ca_relation_name=self._endpoint_mapping["tls-certificates"].name
            if "tls-certificates" in self._endpoint_mapping
            else None,
        )
        self._workload_tracing = TracingEndpointRequirer(
            charm,
            relation_name=self._endpoint_mapping["workload-tracing"].name,
            protocols=workload_tracing_protocols,
        )

        self._metrics_endpoint = MetricsEndpointProvider(
            charm,
            relation_name=self._endpoint_mapping["prometheus-scrape"].name,
            jobs=prometheus_scrape_jobs,
        )

        self._grafana_dashboards = GrafanaDashboardProvider(
            charm,
            relation_name=self._endpoint_mapping["grafana-dashboard"].name,
        )

    def get_workload_tracing_endpoints(self, protocol: ReceiverProtocol) -> Tuple[str, ...]:
        """Retrieve the workload tracing endpoint from the workload-tracing integration, if any."""
        tracing = self._workload_tracing
        return tuple(
            tracing.get_endpoint(protocol, relation=relation) for relation in tracing.relations
        )

    def _validate_endpoints(self, charm):
        # verify that the charm's metadata has declared all required endpoints
        for endpoint in self._endpoint_mapping.values():
            ep_meta = charm.meta.requires.get(
                endpoint.name, charm.meta.provides.get(endpoint.name)
            )
            if ep_meta is None:
                raise ValueError(f"Charm is missing a required endpoint: {endpoint}")
            if ep_meta.interface_name != endpoint.interface:
                raise ValueError(
                    f"Charm's endpoint {endpoint.name} has wrong interface name "
                    f"(expected {endpoint.interface}, got {ep_meta.interface_name})"
                )
