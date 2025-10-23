# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charmed Operator for Litmus Chaoscenter; the frontend for a chaos testing platform."""

import logging
import socket
from typing import Optional, Dict, cast

from charms.tls_certificates_interface.v4.tls_certificates import (
    TLSCertificatesRequiresV4,
    CertificateRequestAttributes,
)
from ops.charm import CharmBase
from ops import (
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
from nginx_config import get_config, http_server_port, all_pebble_checks, container_name
from traefik_config import ingress_config, static_ingress_config

from charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider
from charms.traefik_k8s.v0.traefik_route import TraefikRouteRequirer

from litmus_libs import get_app_hostname, get_litmus_version
from litmus_libs.interfaces.http_api import (
    LitmusAuthApiRequirer,
    LitmusBackendApiRequirer,
)
from litmus_libs.interfaces.self_monitoring import SelfMonitoring
from charms.tempo_coordinator_k8s.v0.tracing import TracingEndpointRequirer
import cosl
import cosl.reconciler


logger = logging.getLogger(__name__)
AUTH_HTTP_API_ENDPOINT = "auth-http-api"
BACKEND_HTTP_API_ENDPOINT = "backend-http-api"
TLS_CERTIFICATES_ENDPOINT = "tls-certificates"
NGINX_EXPORTER_PORT = 9113

NGINX_OVERRIDES: NginxMappingOverrides = {
    "nginx_port": http_server_port,
    "nginx_exporter_port": NGINX_EXPORTER_PORT,
}


class LitmusChaoscenterCharm(CharmBase):
    """Charmed Operator for Litmus Chaoscenter."""

    def __init__(self, *args):
        super().__init__(*args)
        self._fqdn = socket.getfqdn()
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
        self._metrics_endpoint_provider = MetricsEndpointProvider(
            self,
            jobs=[
                {
                    "static_configs": [
                        {"targets": [f"{self._fqdn}:{NGINX_EXPORTER_PORT}"]}
                    ]
                }
            ],
        )

        self._workload_tracing = TracingEndpointRequirer(
            self,
            relation_name="workload-tracing",
            protocols=["otlp_grpc"],
        )

        self.nginx = Nginx(
            self,
            options=None,
            container_name=container_name,
            liveness_check_endpoint_getter=self._nginx_liveness_endpoint,
        )

        self._self_monitoring = SelfMonitoring(self)

        self.nginx_exporter = NginxPrometheusExporter(
            self,
            options=NGINX_OVERRIDES,
        )

        self.framework.observe(
            self.on.collect_unit_status, self._on_collect_unit_status
        )

        cosl.reconciler.observe_events(
            self, cosl.reconciler.all_events, self._reconcile
        )

    def _reconcile(self):
        """Run all logic that is independent of what event we're processing."""
        self.unit.set_ports(http_server_port)
        self.unit.set_workload_version(
            get_litmus_version(
                container=self.unit.get_container(container_name),
            )
            or ""
        )

        self._metrics_endpoint_provider.set_scrape_job_spec()
        self._self_monitoring.reconcile(
            ca_cert=self._tls_config.ca_cert if self._tls_config else None
        )

        if None in self.consistency_checks.values():
            # a None in consistency check results means: check failed
            # we skip nginx reconcile because for it to succeed, we need auth/backend urls,
            # and tls consistency.
            logger.info("deployment inconsistent; skipping nginx reconcile")

        else:
            self.nginx.reconcile(
                nginx_config=self._nginx_config(
                    # consistency checks would fail if these were unset
                    auth_url=cast(str, self.auth_url),
                    backend_url=cast(str, self.backend_url),
                ),
                tls_config=self._tls_config,
            )
            self.nginx_exporter.reconcile()

        self._receive_backend_http_api.publish_endpoint(
            f"{self._most_external_frontend_url}:{http_server_port}"
        )

        if self.unit.is_leader() and self.ingress.is_ready():
            self.ingress.submit_to_traefik(
                ingress_config(
                    self.model.name, self.app.name, self._tls_config is not None
                ),
                static=static_ingress_config(),
            )

    ##################
    # CONFIG METHODS #
    ##################

    def _nginx_tracing_config(self) -> Optional[NginxTracingConfig]:
        endpoint = (
            self._workload_tracing.get_endpoint("otlp_grpc")
            if self._workload_tracing.is_ready()
            else None
        )
        return (
            NginxTracingConfig(
                endpoint=endpoint,
                service_name=f"{self.app.name}-nginx",  # append "-nginx" suffix to distinguish workload traces from charm traces
                # insert juju topology into the trace resource attributes
                resource_attributes={
                    "juju_{}".format(key): value
                    for key, value in cosl.JujuTopology.from_charm(self)
                    .as_dict()
                    .items()
                    if value
                },
            )
            if endpoint
            else None
        )

    def _nginx_config(self, backend_url: str, auth_url: str) -> str:
        return get_config(
            hostname=self._fqdn,
            auth_url=auth_url,
            backend_url=backend_url,
            tls_available=bool(self._tls_config),
            tracing_config=self._nginx_tracing_config(),
        )

    @property
    def _certificate_request_attributes(self) -> CertificateRequestAttributes:
        return CertificateRequestAttributes(
            common_name=self.app.name,
            sans_dns=frozenset(
                (
                    self._fqdn,
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

    def _nginx_liveness_endpoint(self, tls: bool) -> str:
        return f"http{'s' if tls else ''}://{self._fqdn}:{http_server_port}/health"

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
            return f"{self.ingress.scheme}://{self.ingress.external_host}"
        return self._internal_frontend_url

    @property
    def _internal_frontend_url(self):
        """Internal (i.e. not ingressed) url."""
        protocol = "https" if self._tls_config else "http"
        return f"{protocol}://{get_app_hostname(self.app.name, self.model.name)}"

    @property
    def backend_url(self):
        """The backend's http API url."""
        return self._receive_backend_http_api.backend_endpoint

    @property
    def auth_url(self):
        """The auth's http API url."""
        return self._receive_auth_http_api.auth_endpoint

    ###################
    # UTILITY METHODS #
    ###################

    @property
    def consistency_checks(self) -> Dict[str, Optional[bool]]:
        """Verify the control plane deployment is consistent.

        - check that we have auth and backend endpoint URLs
        - check that if auth OR backend are giving us a https endpoint, we also have a TLS relation
        """
        # to function, the frontend needs backend and auth servers URLs.
        inconsistencies = {
            # we need an auth API endpoint
            "auth http API endpoint url": self.auth_url,
            # we need a backend API endpoint
            "backend http API endpoint url": self.backend_url,
            # if either auth or backend are on tls, we should have a tls relation too
            # StatusManager API demands 'None' to fail this check
            "tls certificate": None if self._is_missing_tls_certificate else "ok",
        }
        return inconsistencies

    @property
    def _is_missing_tls_certificate(self) -> bool:
        """Return whether this unit needs a tls certificate to function."""
        # if auth or backend are integrated with TLS, but this charm isn't, we have a problem
        #  cfr. https://github.com/canonical/litmus-operators/issues/94
        any_endpoint_https = any(
            endpoint.startswith("https://")
            for endpoint in (self.auth_url, self.backend_url)
            if endpoint
        )
        if any_endpoint_https and not self._tls_config:
            return True

        return False

    ###################
    # EVENT OBSERVERS #
    ###################

    def _on_collect_unit_status(self, e: CollectStatusEvent):
        required_relations = [
            AUTH_HTTP_API_ENDPOINT,
            BACKEND_HTTP_API_ENDPOINT,
        ]
        if self._is_missing_tls_certificate:
            required_relations.append(TLS_CERTIFICATES_ENDPOINT)

        StatusManager(
            charm=self,
            block_if_relations_missing=required_relations,
            wait_for_config=self.consistency_checks,
            block_if_pebble_checks_failing={
                container_name: all_pebble_checks,
            },
        ).collect_status(e)
        e.add_status(
            ActiveStatus(
                f"Ready at {self._most_external_frontend_url}:{http_server_port}."
            )
        )


if __name__ == "__main__":  # pragma: nocover
    from ops import main

    main(LitmusChaoscenterCharm)  # noqa
