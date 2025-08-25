# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charmed Operator for Litmus Authentication server; the auth layer for a chaos testing platform."""

import logging
from typing import Optional

from ops.charm import CharmBase

from litmus_auth import LitmusAuth
from cosl.reconciler import all_events, observe_events
from ops import ActiveStatus, CollectStatusEvent, BlockedStatus, WaitingStatus
from pydantic_core import ValidationError
from charms.data_platform_libs.v0.data_interfaces import (
    DatabaseRequires,
)
from litmus_libs.interfaces import LitmusAuthDataProvider, Endpoint
from litmus_libs import app_hostname, DatabaseConfig

logger = logging.getLogger(__name__)


class LitmusAuthCharm(CharmBase):
    """Charmed Operator for Litmus Authentication server."""

    def __init__(self, *args):
        super().__init__(*args)

        self.unit.set_ports(LitmusAuth.http_port, LitmusAuth.grpc_port)
        self._auth_provider = LitmusAuthDataProvider(
            self.model.get_relation("litmus-auth"),
            self.app,
        )

        self._database = DatabaseRequires(
            self,
            relation_name="database",
            database_name="admin",
            # throughout its lifecycle, litmus will need to create and manage new databases (e.g. `auth` and `litmus`)
            # to do this, it requires cluster-wide permissions that are only part of the `admin` role.
            # cfr. https://github.com/canonical/mongo-single-kernel-library/blob/6/edge/single_kernel_mongo/utils/mongodb_users.py#L52
            extra_user_roles="admin",
        )

        self.litmus_auth = LitmusAuth(
            container=self.unit.get_container(LitmusAuth.name),
            db_config=self.database_config,
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
        if not self._database.relations:
            e.add_status(BlockedStatus("Missing MongoDB integration."))
        if not self.model.relations["litmus-auth"]:
            e.add_status(BlockedStatus("Missing litmus-auth integration."))
        if not self.database_config:
            e.add_status(WaitingStatus("MongoDB config not ready."))
        if not self.backend_grpc_endpoint:
            e.add_status(
                WaitingStatus("Backend server has not provided its gRPC endpoint yet.")
            )
        e.add_status(ActiveStatus(""))

    ###################
    # UTILITY METHODS #
    ###################
    def _reconcile(self):
        """Run all logic that is independent of what event we're processing."""
        self.litmus_auth.reconcile()
        if self.unit.is_leader():
            self._auth_provider.publish_endpoint(
                Endpoint(
                    grpc_server_host=app_hostname(self.app.name, self.model.name),
                    grpc_server_port=LitmusAuth.grpc_port,
                    # TODO: check if TLS is enabled once https://github.com/canonical/litmus-operators/issues/25 is fixed
                    insecure=True,
                )
            )


if __name__ == "__main__":  # pragma: nocover
    from ops import main

    main(LitmusAuthCharm)  # noqa
