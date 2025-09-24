# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charmed Operator for Litmus Chaoscenter; the frontend for a chaos testing platform."""

import logging
import socket
from typing import Optional

from charms.tls_certificates_interface.v4.tls_certificates import (
    TLSCertificatesRequiresV4,
    CertificateRequestAttributes,
)
from ops.charm import CharmBase
from ops import (
    LifecycleEvent,
    EventBase,
    CollectStatusEvent,
    ActiveStatus,
)
from coordinated_workers.models import TLSConfig
from coordinated_workers.nginx import (
    Nginx,
    NginxPrometheusExporter,
    NginxMappingOverrides,
    NginxTracingConfig,
)

from litmus_libs.status_manager import StatusManager
from nginx_config import get_config, http_server_port
from traefik_config import ingress_config, static_ingress_config

from charms.traefik_k8s.v0.traefik_route import TraefikRouteRequirer

from litmus_libs import get_app_hostname, get_litmus_version
from litmus_libs.interfaces.http_api import (
    LitmusAuthApiRequirer,
    LitmusBackendApiRequirer,
)
from litmus_libs.interfaces.self_monitoring import SelfMonitoring
from charms.tempo_coordinator_k8s.v0.tracing import TracingEndpointRequirer
from cosl import JujuTopology


logger = logging.getLogger(__name__)
AUTH_HTTP_API_ENDPOINT = "auth-http-api"
BACKEND_HTTP_API_ENDPOINT = "backend-http-api"
TLS_CERTIFICATES_ENDPOINT = "tls-certificates"

NGINX_OVERRIDES: NginxMappingOverrides = {
    "nginx_port": http_server_port,
    "nginx_exporter_port": 9113,
}


class LitmusChaoscenterCharm(CharmBase):
    """Charmed Operator for Litmus Chaoscenter."""

    def __init__(self, *args):
        super().__init__(*args)
        self._receive_auth_http_api = LitmusAuthApiRequirer(
            relation=self.model.get_relation(AUTH_HTTP_API_ENDPOINT), app=self.app
        )
        self._receive_backend_http_api = LitmusBackendApiRequirer(
            relation=self.model.get_relation(BACKEND_HTTP_API_ENDPOINT), app=self.app
        )
        self._tls_certificates = TLSCertificatesRequiresV4(
            charm=self,
            relationship_name=TLS_CERTIFICATES_ENDPOINT,
            certificate_requests=[self._certificate_request_attributes],
        )
        self.ingress = TraefikRouteRequirer(
            self,
            self.model.get_relation("ingress"),  # type: ignore
            "ingress",
        )

        self._workload_tracing = TracingEndpointRequirer(
            self,
            relation_name="workload-tracing",
            protocols=["otlp_grpc"],
        )

        self.nginx = Nginx(
            self,
            config_getter=self._nginx_config,
            tls_config_getter=lambda: self._tls_config,
            options=None,
            container_name="chaoscenter",
        )

        self._self_monitoring = SelfMonitoring(self)

        self.nginx_exporter = NginxPrometheusExporter(
            self,
            options=NGINX_OVERRIDES,
        )

        self.framework.observe(
            self.on.collect_unit_status, self._on_collect_unit_status
        )

        for event in self.on.events().values():
            # ignore LifecycleEvents: we want to execute the reconciler exactly once per juju hook.
            if issubclass(event.event_type, LifecycleEvent):
                continue
            self.framework.observe(event, self._on_any_event)

    ##################
    # CONFIG METHODS #
    ##################

    def _nginx_tracing_config(self) -> Optional[NginxTracingConfig]:
        endpoint = self._workload_tracing_endpoint
        return (
            NginxTracingConfig(
                endpoint=endpoint,
                service_name=f"{self.app.name}-workload",  # append "-workload" suffix to distinguish workload traces from charm traces
                # insert juju topology into the trace resource attributes
                resource_attributes={
                    "juju_{}".format(key): value
                    for key, value in JujuTopology.from_charm(self).as_dict().items()
                    if value
                },
            )
            if endpoint
            else None
        )

    def _nginx_config(self, tls: bool) -> str:
        return get_config(
            hostname=socket.getfqdn(),
            auth_url=self.auth_url,
            backend_url=self.backend_url,
            tls_available=tls,
            tracing_config=self._nginx_tracing_config(),
        )

    ##################
    # EVENT HANDLERS #
    ##################
    @property
    def _most_external_frontend_url(self):
        """Litmus ChaosCenter URL.

        Ingressed URL, if related to ingress, otherwise internal url.
        """
        if (
            self.ingress.is_ready()
            and self.ingress.scheme
            and self.ingress.external_host
        ):
            return f"{self.ingress.scheme}://{self.ingress.external_host}:8185"
        return self._internal_frontend_url

    @property
    def _internal_frontend_url(self):
        """Internal (i.e. not ingressed) url."""
        protocol = "https" if self._tls_config else "http"
        return f"{protocol}://{get_app_hostname(self.app.name, self.model.name)}:8185"

    @property
    def backend_url(self):
        """The backend's http API url."""
        return self._receive_backend_http_api.backend_endpoint

    @property
    def auth_url(self):
        """The auth's http API url."""
        return self._receive_auth_http_api.auth_endpoint

    def _on_any_event(self, _: EventBase):
        """Common entry hook."""
        self._reconcile()
        self._receive_backend_http_api.publish_endpoint(
            self._most_external_frontend_url
        )

    def _on_collect_unit_status(self, e: CollectStatusEvent):
        StatusManager(
            charm=self,
            block_if_relations_missing=(
                AUTH_HTTP_API_ENDPOINT,
                BACKEND_HTTP_API_ENDPOINT,
            ),
            wait_for_config={
                "backend http API endpoint url": self.backend_url,
                "auth http API endpoint url": self.auth_url,
            },
        ).collect_status(e)
        # TODO: add pebble check to verify frontend is up
        #  https://github.com/canonical/litmus-operators/issues/36
        e.add_status(ActiveStatus(f"Ready at {self._most_external_frontend_url}."))

    ###################
    # UTILITY METHODS #
    ###################
    def _reconcile(self):
        """Run all logic that is independent of what event we're processing."""
        self.unit.set_ports(http_server_port)
        self.unit.set_workload_version(
            get_litmus_version(
                container=self.unit.get_container("chaoscenter"),
            )
            or ""
        )
        self._self_monitoring.reconcile(
            ca_cert=self._tls_config.ca_cert if self._tls_config else None
        )
        if self.backend_url and self.auth_url:
            self.nginx.reconcile()
            self.nginx_exporter.reconcile()
        if self.unit.is_leader() and self.ingress.is_ready():
            self.ingress.submit_to_traefik(
                ingress_config(
                    self.model.name, self.app.name, self._tls_config is not None
                ),
                static=static_ingress_config(),
            )

    @property
    def _certificate_request_attributes(self) -> CertificateRequestAttributes:
        return CertificateRequestAttributes(
            common_name=self.app.name,
            sans_dns=frozenset(
                (
                    socket.getfqdn(),
                    get_app_hostname(self.app.name, self.model.name),
                    # TODO: Once Ingress is in use, its address should also be added here
                )
            ),
        )

    @property
    def _tls_config(self) -> Optional[TLSConfig]:
        """Returns the TLS configuration, including certificates and private key, if available; None otherwise."""
        certificates, private_key = self._tls_certificates.get_assigned_certificate(
            self._certificate_request_attributes
        )
        if not (certificates and private_key):
            return None
        return TLSConfig(
            server_cert=certificates.certificate.raw,
            private_key=private_key.raw,
            ca_cert=certificates.ca.raw,
        )

    @property
    def _workload_tracing_endpoint(self) -> Optional[str]:
        if self._workload_tracing.is_ready():
            endpoint = self._workload_tracing.get_endpoint("otlp_grpc")
            return endpoint
        return None


if __name__ == "__main__":  # pragma: nocover
    from ops import main

    main(LitmusChaoscenterCharm)  # noqa
