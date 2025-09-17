# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charmed Operator for Litmus Authentication server; the auth layer for a chaos testing platform."""

import logging
import socket
from typing import Optional

from ops.charm import CharmBase

from charms.tls_certificates_interface.v4.tls_certificates import (
    TLSCertificatesRequiresV4,
    CertificateRequestAttributes,
)
from litmus_auth import LitmusAuth
from cosl.reconciler import all_events, observe_events
from ops import ActiveStatus, CollectStatusEvent, BlockedStatus, WaitingStatus
from pydantic_core import ValidationError
from charms.data_platform_libs.v0.data_interfaces import (
    DatabaseRequires,
)
from litmus_libs.interfaces.litmus_auth import LitmusAuthProvider, Endpoint
from litmus_libs import (
    DatabaseConfig,
    TLSConfigData,
    TlsReconciler,
    get_app_hostname,
    get_litmus_version,
)
from litmus_libs.interfaces.http_api import LitmusAuthApiProvider

DATABASE_ENDPOINT = "database"
LITMUS_AUTH_ENDPOINT = "litmus-auth"
TLS_CERTIFICATES_ENDPOINT = "tls-certificates"
# TODO: Put cert paths in the tls_reconciler module in litmus-libs
TLS_CERT_PATH = "/etc/tls/tls.crt"
TLS_KEY_PATH = "/etc/tls/tls.key"
TLS_CA_PATH = "/usr/local/share/ca-certificates/ca.crt"

logger = logging.getLogger(__name__)


class LitmusAuthCharm(CharmBase):
    """Charmed Operator for Litmus Authentication server."""

    def __init__(self, *args):
        super().__init__(*args)

        self._auth_provider = LitmusAuthProvider(
            self.model.get_relation(LITMUS_AUTH_ENDPOINT),
            self.app,
        )

        self._database = DatabaseRequires(
            self,
            relation_name=DATABASE_ENDPOINT,
            database_name="admin",
            # throughout its lifecycle, litmus will need to create and manage new databases (e.g. `auth` and `litmus`)
            # to do this, it requires cluster-wide permissions that are only part of the `admin` role.
            # cfr. https://github.com/canonical/mongo-single-kernel-library/blob/6/edge/single_kernel_mongo/utils/mongodb_users.py#L52
            extra_user_roles="admin",
        )
        self._tls_certificates = TLSCertificatesRequiresV4(
            charm=self,
            relationship_name=TLS_CERTIFICATES_ENDPOINT,
            certificate_requests=[self._certificate_request_attributes],
        )

        self._send_http_api = LitmusAuthApiProvider(
            self.model.get_relation("http-api"), app=self.app
        )

        self._tls = TlsReconciler(
            container=self.unit.get_container(LitmusAuth.name),
            tls_cert_path=TLS_CERT_PATH,
            tls_key_path=TLS_KEY_PATH,
            tls_ca_path=TLS_CA_PATH,
            tls_config_getter=lambda: self._tls_config,
        )
        self.litmus_auth = LitmusAuth(
            container=self.unit.get_container(LitmusAuth.name),
            db_config=self.database_config,
            tls_config_getter=lambda: self._tls_config,
            tls_cert_path=TLS_CERT_PATH,
            tls_key_path=TLS_KEY_PATH,
            tls_ca_path=TLS_CA_PATH,
            backend_grpc_endpoint=self.backend_grpc_endpoint,
        )

        self.framework.observe(
            self.on.collect_unit_status, self._on_collect_unit_status
        )

        observe_events(self, all_events, self._reconcile)

    @property
    def database_config(self) -> Optional[DatabaseConfig]:
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
    def backend_grpc_endpoint(self) -> Optional[Endpoint]:
        return self._auth_provider.get_backend_grpc_endpoint()

    ##################
    # EVENT HANDLERS #
    ##################

    def _on_collect_unit_status(self, e: CollectStatusEvent):
        missing_relations = [
            rel
            for rel in (DATABASE_ENDPOINT, LITMUS_AUTH_ENDPOINT)
            if not self.model.get_relation(rel)
        ]
        missing_configs = [
            config_name
            for config_name, source in (
                ("database config", self.database_config),
                ("backend gRPC endpoint", self.backend_grpc_endpoint),
            )
            if not source
        ]
        if missing_relations:
            e.add_status(
                BlockedStatus(
                    f"Missing [{', '.join(missing_relations)}] integration(s)."
                )
            )
        if missing_configs:
            e.add_status(
                WaitingStatus(f"[{', '.join(missing_configs)}] not provided yet.")
            )

        # TODO: add pebble check to verify auth server is up
        #  https://github.com/canonical/litmus-operators/issues/36
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
        self._tls_certificates.sync()
        self._tls.reconcile()
        self.litmus_auth.reconcile()
        self.unit.set_ports(*self.litmus_auth.litmus_auth_ports)
        self.unit.set_workload_version(
            get_litmus_version(self.unit.get_container(LitmusAuth.name)) or ""
        )
        if self.unit.is_leader():
            self._auth_provider.publish_endpoint(
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
            self.litmus_auth.https_port
            if self._tls_ready
            else self.litmus_auth.http_port
        )

    @property
    def _grpc_port(self):
        return (
            self.litmus_auth.grpc_tls_port
            if self._tls_ready
            else self.litmus_auth.grpc_port
        )


if __name__ == "__main__":  # pragma: nocover
    from ops import main

    main(LitmusAuthCharm)  # noqa
