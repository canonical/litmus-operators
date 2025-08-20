# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charmed Operator for Litmus Chaoscenter; the frontend for a chaos testing platform."""

import logging
from typing import Optional

from ops.charm import CharmBase
from ops import ActiveStatus, CollectStatusEvent, BlockedStatus, WaitingStatus
from pydantic_core import ValidationError
from charms.data_platform_libs.v0.data_interfaces import (
    DatabaseRequires,
)
from litmus_frontend import LitmusFrontend
from cosl.reconciler import all_events, observe_events
from models import DatabaseConfig

logger = logging.getLogger(__name__)


class LitmusChaoscenterCharm(CharmBase):
    """Charmed Operator for Litmus Chaoscenter."""

    def __init__(self, *args):
        super().__init__(*args)

        self.unit.set_ports(LitmusFrontend.port)

        self._database = DatabaseRequires(
            self,
            relation_name="database",
            database_name="admin",
            # throughout its lifecycle, litmus will need to create and manage new databases (e.g. `auth` and `litmus`)
            # to do this, it requires cluster-wide permissions that are only part of the `admin` role.
            # cfr. https://github.com/canonical/mongo-single-kernel-library/blob/6/edge/single_kernel_mongo/utils/mongodb_users.py#L52
            extra_user_roles="admin",
        )

        self.litmus_frontend = LitmusFrontend(
            container=self.unit.get_container(LitmusFrontend.name),
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
        if not self.database_config:
            e.add_status(WaitingStatus("MongoDB config not ready."))

        e.add_status(ActiveStatus(""))

    ###################
    # UTILITY METHODS #
    ###################
    def _reconcile(self):
        """Run all logic that is independent of what event we're processing."""
        self.litmus_frontend.reconcile()


if __name__ == "__main__":  # pragma: nocover
    from ops import main

    main(LitmusChaoscenterCharm)  # noqa
