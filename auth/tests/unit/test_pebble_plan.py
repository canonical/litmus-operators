# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
from ops.testing import State


def test_pebble_ready_plan(ctx, authserver_container):
    expected_plan = {
        "services": {
            "authserver": {
                "override": "replace",
                "summary": "litmus auth server layer",
                "command": "/litmus/server",
                "startup": "enabled",
            }
        },
    }

    # GIVEN no relations
    state = State(containers=[authserver_container], relations=[])

    # WHEN a workload pebble ready event is fired
    state_out = ctx.run(ctx.on.pebble_ready(authserver_container), state=state)

    # THEN litmus auth server pebble plan is generated
    authserver_container_out = state_out.get_container(authserver_container.name)
    assert authserver_container_out.plan.to_dict() == expected_plan
    # AND the pebble service is NOT running
    assert not authserver_container_out.services.get("authserver").is_running()

    # AND the charm status is blocked
    assert state_out.unit_status.name == "blocked"
