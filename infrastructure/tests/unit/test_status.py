# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest
import ops
from ops.testing import State, CharmEvents


# TODO: we'll probably update the test once we have some real logic in the charm,
# but for now let's just check that the charm sets active on all events.
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
    # GIVEN a running charm container

    # WHEN we receive any event
    state_out = ctx.run(
        event,
        State(),
    )
    # THEN the unit sets active
    assert isinstance(state_out.unit_status, ops.ActiveStatus)
