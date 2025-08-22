# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest
import ops
from ops.testing import State, CharmEvents


@pytest.mark.parametrize("leader", (False, True))
@pytest.mark.parametrize(
    "event",
    (
        CharmEvents.upgrade_charm(),
        CharmEvents.install(),
        CharmEvents.update_status(),
        CharmEvents.install(),
    ),
)
def test_blocked_if_no_database_integration(ctx, event, authserver_container, leader):
    # GIVEN a running container
    # AND no database relation
    # WHEN we receive any event
    state_out = ctx.run(event, State(containers={authserver_container}, leader=leader))
    # THEN the unit sets blocked
    assert isinstance(state_out.unit_status, ops.BlockedStatus)


@pytest.mark.parametrize(
    "event",
    (
        CharmEvents.upgrade_charm(),
        CharmEvents.install(),
        CharmEvents.update_status(),
        CharmEvents.install(),
    ),
)
def test_waiting_if_no_database_config(
    ctx, event, database_relation, authserver_container
):
    # GIVEN a running container
    # AND a database relation
    # AND remote hasn't sent any data yet
    # WHEN we receive any event
    state_out = ctx.run(
        event, State(containers={authserver_container}, relations={database_relation})
    )
    # THEN the unit sets waiting
    assert isinstance(state_out.unit_status, ops.WaitingStatus)
