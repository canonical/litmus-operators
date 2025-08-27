# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charmed Operator for Litmus Backend server; the backend layer for a chaos testing platform."""

import logging
import socket

from ops.charm import CharmBase

from litmus_backend import LitmusBackend
from cosl.reconciler import all_events, observe_events
from models import DatabaseConfig

from ops import ActiveStatus, CollectStatusEvent, BlockedStatus, WaitingStatus
from pydantic_core import ValidationError
from charms.data_platform_libs.v0.data_interfaces import (
    DatabaseRequires,
)
from typing import Optional
from litmus_libs.interfaces import http_api

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

        self._send_http_api = http_api.LitmusAuthApiProvider(
            self.model.get_relation("http-api"), app=self.app
        )

        self.litmus_backend = LitmusBackend(
            container=self.unit.get_container(LitmusBackend.name),
            db_config=self.database_config,
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

    ##################
    # EVENT HANDLERS #
    ##################

    def _on_collect_unit_status(self, e: CollectStatusEvent):
        if not self._database.relations:
            e.add_status(BlockedStatus("Missing MongoDB integration."))
        # TODO: set to blocked if `litmus_auth` integration is not present
        # https://github.com/canonical/litmus-operators/issues/17
        if not self.database_config:
            e.add_status(WaitingStatus("MongoDB config not ready."))

        e.add_status(ActiveStatus(""))

    ###################
    # UTILITY METHODS #
    ###################
    @property
    def _http_api_endpoint(self):
        """Internal (i.e. not ingressed) url."""
        return f"http://{socket.getfqdn()}:{self.litmus_backend.http_port}"

    def _reconcile(self):
        """Run all logic that is independent of what event we're processing."""
        self.litmus_backend.reconcile()
        self._send_http_api.publish_endpoint(self._http_api_endpoint)


if __name__ == "__main__":  # pragma: nocover
    from ops import main

    main(LitmusBackendCharm)  # noqa
