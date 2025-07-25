# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
from ops.testing import State


def test_pebble_ready_plan(ctx, nginx_container):
    expected_plan = {
        "services": {
            "nginx": {
                "override": "replace",
                "summary": "litmus frontend layer",
                "command": "nginx -g 'daemon off;'",
                "startup": "enabled",
            }
        },
    }

    # GIVEN no relations
    state = State(containers=[nginx_container], relations=[])

    # WHEN a workload pebble ready event is fired
    state_out = ctx.run(ctx.on.pebble_ready(nginx_container), state=state)

    # THEN litmus auth server pebble plan is generated
    nginx_container_out = state_out.get_container(nginx_container.name)
    assert nginx_container_out.plan.to_dict() == expected_plan
    # AND the pebble service is NOT running
    assert not nginx_container_out.services.get("nginx").is_running()

    # AND the charm status is blocked
    assert state_out.unit_status.name == "blocked"
