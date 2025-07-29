# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
from ops.testing import State


def test_pebble_ready_plan(ctx, backend_container):
    expected_plan = {
        "services": {
            "litmuschaos-server": {
                "override": "replace",
                "summary": "litmus backend server layer",
                "command": "server",
                "startup": "enabled",
            }
        },
    }

    # GIVEN no relations
    state = State(containers=[backend_container], relations=[])

    # WHEN a workload pebble ready event is fired
    state_out = ctx.run(ctx.on.pebble_ready(backend_container), state=state)

    # THEN litmus backend server pebble plan is generated
    backend_container_out = state_out.get_container(backend_container.name)
    assert backend_container_out.plan.to_dict() == expected_plan
    # AND the pebble service is NOT running
    assert not backend_container_out.services.get("litmuschaos-server").is_running()

    # AND the charm status is blocked
    assert state_out.unit_status.name == "blocked"
