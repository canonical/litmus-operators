# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest
import ops
from ops.testing import Relation, State, CharmEvents


@pytest.mark.parametrize(
    "event",
    (
        CharmEvents.upgrade_charm(),
        CharmEvents.install(),
        CharmEvents.update_status(),
        CharmEvents.install(),
    ),
)
def test_active_status(ctx, event):
    # GIVEN a charm with the litmus-infrastructure relation joined
    infra_rel = Relation(endpoint="litmus-infrastructure")

    # WHEN we receive any standard lifecycle event
    state_out = ctx.run(
        event,
        state=State(
            relations={infra_rel},
            leader=True,
        ),
    )

    # THEN the unit sets active because the dependency is met
    assert isinstance(state_out.unit_status, ops.ActiveStatus)


def test_blocked_status_missing_relation(ctx):
    # GIVEN a charm with NO relations

    # WHEN an event fires
    state_out = ctx.run(
        "update-status",
        state=State(relations=set()),
    )

    # THEN the unit status is Blocked
    assert isinstance(state_out.unit_status, ops.BlockedStatus)
