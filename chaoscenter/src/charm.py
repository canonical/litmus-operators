# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charmed Operator for Litmus Chaoscenter; the frontend for a chaos testing platform."""

import logging

from ops.charm import CharmBase
from ops import LifecycleEvent, EventBase, CollectStatusEvent, BlockedStatus

from litmus_frontend import LitmusFrontend

logger = logging.getLogger(__name__)


class LitmusChaoscenterCharm(CharmBase):
    """Charmed Operator for Litmus Chaoscenter."""

    def __init__(self, *args):
        super().__init__(*args)
        self.litmus_frontend = LitmusFrontend(
            container=self.unit.get_container(LitmusFrontend.name),
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
    # EVENT HANDLERS #
    ##################
    def _on_any_event(self, _: EventBase):
        """Common entry hook."""
        self._reconcile()

    def _on_collect_unit_status(self, e: CollectStatusEvent):
        # FIXME: add a condition to set to blocked if we don't have a valid config from relation data
        e.add_status(BlockedStatus("Missing config"))

    ###################
    # UTILITY METHODS #
    ###################
    def _reconcile(self):
        """Run all logic that is independent of what event we're processing."""
        self.litmus_frontend.reconcile()


if __name__ == "__main__":  # pragma: nocover
    from ops import main

    main(LitmusChaoscenterCharm)  # noqa
