# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import ops
from ops.testing import State, CheckInfo, CharmEvents
from dataclasses import replace
from ops.pebble import Layer
from ops.pebble import CheckStatus
import pytest


@pytest.mark.parametrize(
    "event",
    (
        CharmEvents.upgrade_charm(),
        CharmEvents.install(),
        CharmEvents.update_status(),
        CharmEvents.install(),
    ),
)
def test_pebble_check_failing_blocked_status(
    ctx,
    nginx_container,
    nginx_prometheus_exporter_container,
    auth_http_api_relation,
    backend_http_api_relation,
    event,
):
    # GIVEN relations with auth and backend endpoints
    # AND a chaoscenter container with failing pebble checks
    nginx_container = replace(
        nginx_container,
        layers={
            "chaoscenter": Layer(
                {
                    "services": {"chaoscenter": {}},
                    "checks": {
                        "chaoscenter": {
                            "threshold": 3,
                            "startup": "enabled",
                            "level": None,
                        }
                    },
                }
            )
        },
        check_infos={CheckInfo("chaoscenter", status=CheckStatus.DOWN, level=None)},
    )
    state = State(
        containers=[nginx_container, nginx_prometheus_exporter_container],
        relations=[auth_http_api_relation, backend_http_api_relation],
    )

    # WHEN any event fires
    state_out = ctx.run(event, state=state)

    # THEN the unit sets blocked
    assert isinstance(state_out.unit_status, ops.BlockedStatus)
