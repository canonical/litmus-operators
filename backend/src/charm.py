# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charmed Operator for Litmus Backend server; the backend layer for a chaos testing platform."""

import logging
import socket

from ops.charm import CharmBase

from charms.tls_certificates_interface.v4.tls_certificates import (
    TLSCertificatesRequiresV4,
    CertificateRequestAttributes,
)
from litmus_backend import LitmusBackend
from ops import ActiveStatus, CollectStatusEvent

from litmus_libs.interfaces.litmus_auth import LitmusAuthRequirer, Endpoint
from litmus_libs import (
    DatabaseConfig,
    TLSConfigData,
    TlsReconciler,
    get_app_hostname,
    get_litmus_version,
)
from cosl.reconciler import all_events, observe_events

from pydantic_core import ValidationError
from charms.data_platform_libs.v0.data_interfaces import (
    DatabaseRequires,
)

from typing import Optional, Dict
from litmus_libs.interfaces.http_api import LitmusBackendApiProvider
from litmus_libs.interfaces.self_monitoring import SelfMonitoring
from litmus_libs.status_manager import StatusManager

DATABASE_ENDPOINT = "database"
LITMUS_AUTH_ENDPOINT = "litmus-auth"
TLS_CERTIFICATES_ENDPOINT = "tls-certificates"
# TODO: Put cert paths in the tls_reconciler module in litmus-libs
TLS_CERT_PATH = "/etc/tls/tls.crt"
TLS_KEY_PATH = "/etc/tls/tls.key"
TLS_CA_PATH = "/usr/local/share/ca-certificates/ca.crt"

logger = logging.getLogger(__name__)


class LitmusBackendCharm(CharmBase):
    """Charmed Operator for Litmus Backend server."""

    def __init__(self, *args):
        super().__init__(*args)
        self._backend_container = self.unit.get_container(LitmusBackend.container_name)

        self._database = DatabaseRequires(
            self,
            relation_name=DATABASE_ENDPOINT,
            database_name="admin",
            # throughout its lifecycle, litmus will need to create and manage new databases (e.g. `auth` and `litmus`)
            # to do this, it requires cluster-wide permissions that are only part of the `admin` role.
            # cfr. https://github.com/canonical/mongo-single-kernel-library/blob/6/edge/single_kernel_mongo/utils/mongodb_users.py#L52
            extra_user_roles="admin",
        )
        self._auth = LitmusAuthRequirer(
            self.model.get_relation(LITMUS_AUTH_ENDPOINT),
            self.app,
        )
        self._tls_certificates = TLSCertificatesRequiresV4(
            charm=self,
            relationship_name=TLS_CERTIFICATES_ENDPOINT,
            certificate_requests=[self._certificate_request_attributes],
        )

        self._send_http_api = LitmusBackendApiProvider(
            self.model.get_relation("http-api"), app=self.app
        )

        self._tls = TlsReconciler(
            container=self._backend_container,
            tls_cert_path=TLS_CERT_PATH,
            tls_key_path=TLS_KEY_PATH,
            tls_ca_path=TLS_CA_PATH,
            tls_config_getter=lambda: self._tls_config,
        )
        self.litmus_backend = LitmusBackend(
            container=self._backend_container,
            db_config=self.database_config,
            tls_config_getter=lambda: self._tls_config,
            tls_cert_path=TLS_CERT_PATH,
            tls_key_path=TLS_KEY_PATH,
            tls_ca_path=TLS_CA_PATH,
            auth_grpc_endpoint=self.auth_grpc_endpoint,
            frontend_url=self.frontend_url,
        )

        self._self_monitoring = SelfMonitoring(self)

        self.framework.observe(
            self.on.collect_unit_status, self._on_collect_unit_status
        )

        observe_events(self, all_events, self._reconcile)

    @property
    def database_config(self) -> Optional[DatabaseConfig]:
        """Database configuration."""
        remote_relations_databags = self._database.fetch_relation_data()
        if not remote_relations_databags:
            return None
        # because of limit: 1, we'll only have at most 1 remote relation
        remote_relation_databag = next(iter(remote_relations_databags.values()))
        try:
            return DatabaseConfig(**remote_relation_databag)
        except ValidationError:
            return None

    @property
    def auth_grpc_endpoint(self) -> Optional[Endpoint]:
        """Auth gRPC endpoint."""
        return self._auth.get_auth_grpc_endpoint()

    @property
    def frontend_url(self) -> Optional[str]:
        """Frontend URL."""
        return self._send_http_api.frontend_endpoint

    ##################
    # EVENT HANDLERS #
    ##################
    def _tls_is_consistent(self, remote_insecure: bool) -> bool:
        # if the other end is integrated with TLS, but this charm isn't, we have a problem
        if not remote_insecure and not self._tls_config:
            return False

        return True

    @property
    def consistency_checks(self) -> Dict[str, Optional[bool]]:
        """Verify the control plane deployment is consistent.

        - check that we have an auth endpoint URL
        - check that if auth is giving us a secure endpoint, we also have a TLS relation
        """
        # to function, the frontend needs auth and auth servers URLs.

        auth_endpoint = self.auth_grpc_endpoint
        inconsistencies = {
            # do we have a db relation?
            "database config": self.database_config,
            # do we have the auth's endpoint?
            "auth gRPC endpoint": auth_endpoint,
            # do we have the frontend's url?
            "frontend url": self.frontend_url,
        }

        if auth_endpoint:
            # if auth is on tls, we should have a tls relation too
            # StatusManager API demands 'None' to fail this check
            inconsistencies["tls certificate"] = (
                self._tls_is_consistent(auth_endpoint.insecure) or None
            )
        return inconsistencies

    def _on_collect_unit_status(self, e: CollectStatusEvent):
        required_relations = [
            DATABASE_ENDPOINT,
            LITMUS_AUTH_ENDPOINT,
        ]
        if (grpc_endpoint := self.auth_grpc_endpoint) and not self._tls_is_consistent(
            grpc_endpoint.insecure
        ):
            required_relations.append(TLS_CERTIFICATES_ENDPOINT)

        StatusManager(
            charm=self,
            block_if_relations_missing=required_relations,
            wait_for_config=self.consistency_checks,
            block_if_pebble_checks_failing={
                LitmusBackend.container_name: LitmusBackend.all_pebble_checks
            },
        ).collect_status(e)
        e.add_status(ActiveStatus(""))

    ###################
    # UTILITY METHODS #
    ###################
    @property
    def _tls_config(self) -> Optional[TLSConfigData]:
        """Returns the TLS configuration, including certificates and private key, if available; None otherwise."""
        certificates, private_key = self._tls_certificates.get_assigned_certificate(
            self._certificate_request_attributes
        )
        if not (certificates and private_key):
            return None
        return TLSConfigData(
            server_cert=certificates.certificate.raw,
            private_key=private_key.raw,
            ca_cert=certificates.ca.raw,
        )

    @property
    def _http_api_endpoint(self):
        """Internal (i.e. not ingressed) url."""
        return f"{self._http_api_protocol}://{get_app_hostname(self.app.name, self.model.name)}:{self._http_api_port}"

    @property
    def _certificate_request_attributes(self) -> CertificateRequestAttributes:
        return CertificateRequestAttributes(
            common_name=self.app.name,
            sans_dns=frozenset(
                (
                    socket.getfqdn(),
                    get_app_hostname(self.app.name, self.model.name),
                )
            ),
        )

    def _reconcile(self):
        """Run all logic that is independent of what event we're processing."""
        self.unit.set_ports(*self.litmus_backend.litmus_backend_ports)
        self.unit.set_workload_version(
            get_litmus_version(self._backend_container) or ""
        )
        self._tls_certificates.sync()
        self._tls.reconcile()
        self._self_monitoring.reconcile(
            ca_cert=self._tls_config.ca_cert if self._tls_config else None
        )
        self.litmus_backend.reconcile()
        if self.unit.is_leader():
            self._auth.publish_endpoint(
                Endpoint(
                    grpc_server_host=get_app_hostname(self.app.name, self.model.name),
                    grpc_server_port=self._grpc_port,
                    insecure=False if self._tls_ready else True,
                )
            )
            self._send_http_api.publish_endpoint(self._http_api_endpoint)

    @property
    def _tls_ready(self) -> bool:
        return bool(self._tls_config)

    @property
    def _http_api_protocol(self):
        return "https" if self._tls_ready else "http"

    @property
    def _http_api_port(self):
        return (
            self.litmus_backend.https_port
            if self._tls_ready
            else self.litmus_backend.http_port
        )

    @property
    def _grpc_port(self):
        return (
            self.litmus_backend.grpc_tls_port
            if self._tls_ready
            else self.litmus_backend.grpc_port
        )


if __name__ == "__main__":  # pragma: nocover
    from ops import main

    main(LitmusBackendCharm)  # noqa
