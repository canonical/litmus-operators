# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charmed Operator for Litmus Backend server; the backend layer for a chaos testing platform."""

import logging

from ops.charm import CharmBase

from litmus_backend import LitmusBackend
from ops import ActiveStatus, CollectStatusEvent, BlockedStatus

from litmus_libs.interfaces import LitmusAuthDataRequirer, AuthDataConfig, Endpoint
from litmus_libs import DatabaseConfig, app_hostname
from cosl.reconciler import all_events, observe_events

from ops import WaitingStatus
from pydantic_core import ValidationError
from charms.data_platform_libs.v0.data_interfaces import (
    DatabaseRequires,
)

from typing import Optional

logger = logging.getLogger(__name__)


class LitmusBackendCharm(CharmBase):
    """Charmed Operator for Litmus Backend server."""

    def __init__(self, *args):
        super().__init__(*args)
        self.unit.set_ports(LitmusBackend.http_port, LitmusBackend.grpc_port)

        self._database = DatabaseRequires(
            self,
            relation_name="database",
            database_name="admin",
            # throughout its lifecycle, litmus will need to create and manage new databases (e.g. `auth` and `litmus`)
            # to do this, it requires cluster-wide permissions that are only part of the `admin` role.
            # cfr. https://github.com/canonical/mongo-single-kernel-library/blob/6/edge/single_kernel_mongo/utils/mongodb_users.py#L52
            extra_user_roles="admin",
        )
        self._auth = LitmusAuthDataRequirer(
            self.model.get_relation("litmus-auth"),
            self.app,
            self.model,
        )

        self.litmus_backend = LitmusBackend(
            container=self.unit.get_container(LitmusBackend.name),
            db_config=self.database_config,
            auth_config=self.auth_config,
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
    def auth_config(self) -> Optional[AuthDataConfig]:
        return self._auth.get_auth_data()

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
        if not self.auth_config:
            e.add_status(WaitingStatus("Auth server config not ready."))

        e.add_status(ActiveStatus(""))

    ###################
    # UTILITY METHODS #
    ###################
    def _reconcile(self):
        """Run all logic that is independent of what event we're processing."""
        self.litmus_backend.reconcile()
        if self.unit.is_leader():
            self._auth.publish_endpoint(
                Endpoint(
                    grpc_server_host=app_hostname(self.app.name, self.model.name),
                    grpc_server_port=LitmusBackend.grpc_port,
                    # TODO: check if TLS is enabled once https://github.com/canonical/litmus-operators/issues/23 is fixed
                    insecure=True,
                )
            )


if __name__ == "__main__":  # pragma: nocover
    from ops import main

    main(LitmusBackendCharm)  # noqa
