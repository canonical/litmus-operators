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
from tls import Tls
from ops import ActiveStatus, CollectStatusEvent, BlockedStatus

from litmus_libs.interfaces.litmus_auth import LitmusAuthRequirer, Endpoint
from litmus_libs import DatabaseConfig, get_app_hostname
from cosl.reconciler import all_events, observe_events

from ops import WaitingStatus
from pydantic_core import ValidationError
from charms.data_platform_libs.v0.data_interfaces import (
    DatabaseRequires,
)

from typing import Optional
from litmus_libs.interfaces.http_api import LitmusBackendApiProvider

DATABASE_ENDPOINT = "database"
LITMUS_AUTH_ENDPOINT = "litmus-auth"
TLS_CERTIFICATES_ENDPOINT = "tls-certificates"

logger = logging.getLogger(__name__)


class LitmusBackendCharm(CharmBase):
    """Charmed Operator for Litmus Backend server."""

    def __init__(self, *args):
        super().__init__(*args)
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

        self._tls = Tls(
            container=self.unit.get_container(LitmusBackend.name),
            tls_certificates=self._tls_certificates,
            certificate_request_attributes=self._certificate_request_attributes,
            tls_certificates_relation=self.model.relations.get(
                TLS_CERTIFICATES_ENDPOINT
            ),
        )
        self.litmus_backend = LitmusBackend(
            container=self.unit.get_container(LitmusBackend.name),
            db_config=self.database_config,
            tls_config=self._tls.tls_config,
            auth_grpc_endpoint=self.auth_grpc_endpoint,
            frontend_url=self.frontend_url,
        )

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
                ("auth gRPC endpoint", self.auth_grpc_endpoint),
                ("frontend url", self.frontend_url),
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

        # TODO: add pebble check to verify backend is up
        #  https://github.com/canonical/litmus-operators/issues/36
        e.add_status(ActiveStatus(""))

    ###################
    # UTILITY METHODS #
    ###################
    @property
    def _http_api_endpoint(self):
        """Internal (i.e. not ingressed) url."""
        # TODO: add support for HTTPS once https://github.com/canonical/litmus-operators/issues/23 is fixed
        return f"http://{get_app_hostname(self.app.name, self.model.name)}:{self.litmus_backend.http_port}"

    @property
    def _certificate_request_attributes(self) -> CertificateRequestAttributes:
        return CertificateRequestAttributes(
            common_name=self.app.name,
            sans_dns=frozenset(socket.getfqdn()),
        )

    def _reconcile(self):
        """Run all logic that is independent of what event we're processing."""
        self._tls_certificates.sync()
        self._tls.reconcile()
        self.litmus_backend.reconcile()
        self.unit.set_ports(*self.litmus_backend.litmus_backend_ports)
        if self.unit.is_leader():
            self._auth.publish_endpoint(
                Endpoint(
                    grpc_server_host=get_app_hostname(self.app.name, self.model.name),
                    grpc_server_port=LitmusBackend.grpc_port,
                    # TODO: check if TLS is enabled once https://github.com/canonical/litmus-operators/issues/23 is fixed
                    insecure=True,
                )
            )
            self._send_http_api.publish_endpoint(self._http_api_endpoint)


if __name__ == "__main__":  # pragma: nocover
    from ops import main

    main(LitmusBackendCharm)  # noqa
