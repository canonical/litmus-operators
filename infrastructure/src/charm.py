# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charmed Operator for Litmus Infrastructure; signals the Litmus ChaosCenter to create the infrastructure components required to run chaos experiments"""

import logging

from ops.charm import CharmBase

from cosl.reconciler import all_events, observe_events
from ops import ActiveStatus, CollectStatusEvent
from litmus_libs.status_manager import StatusManager


logger = logging.getLogger(__name__)


class LitmusInfrastructureCharm(CharmBase):
    """Charmed Operator for Litmus Infrastructure."""

    def __init__(self, *args):
        super().__init__(*args)

        self.framework.observe(
            self.on.collect_unit_status, self._on_collect_unit_status
        )

        observe_events(self, all_events, self._reconcile)

    ##################
    # EVENT HANDLERS #
    ##################

    def _on_collect_unit_status(self, e: CollectStatusEvent):

        StatusManager(
            charm=self,
            # TODO: add back when the infrastructure relation is added
            # block_if_relations_missing="litmus-infrastructure",
        ).collect_status(e)
        e.add_status(ActiveStatus(""))

    ###################
    # UTILITY METHODS #
    ###################

    def _reconcile(self):
        """Run all logic that is independent of what event we're processing."""
        # TODO reconcile the infrastructure relation once added
        pass


if __name__ == "__main__":  # pragma: nocover
    from ops import main

    main(LitmusInfrastructureCharm)  # noqa
