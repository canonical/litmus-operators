# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
from ops.testing import State
from dataclasses import replace


def test_pebble_plan_minimal(ctx, authserver_container):
    expected_env_vars = {
        "ALLOWED_ORIGINS",
        "REST_PORT",
        "GRPC_PORT",
        "ADMIN_USERNAME",
        "ADMIN_PASSWORD",
    }

    # GIVEN a running container with no relations
    state = State(containers=[authserver_container], relations=[])

    # WHEN a workload pebble ready event is fired
    state_out = ctx.run(ctx.on.pebble_ready(authserver_container), state=state)

    # THEN litmus auth server pebble plan is generated with the right env vars
    authserver_container_out = state_out.get_container(authserver_container.name)
    actual_env_vars = authserver_container_out.plan.to_dict()["services"]["authserver"][
        "environment"
    ]
    assert actual_env_vars.keys() == expected_env_vars

    # AND the pebble service is NOT running
    assert not authserver_container_out.services.get("authserver").is_running()


def test_pebble_plan_with_database_relation(
    ctx, authserver_container, database_relation
):
    expected_env_vars = {
        "DB_USER",
        "DB_PASSWORD",
        "DB_SERVER",
    }
    # GIVEN a running container with a database relation
    database_relation = replace(
        database_relation,
        remote_app_data={
            "username": "admin",
            "password": "pass",
            "uris": "uri.fqdn.1:port,uri.fqdn.2:port",
        },
    )
    state = State(containers=[authserver_container], relations=[database_relation])

    # WHEN a relation changed event is fired
    state_out = ctx.run(ctx.on.relation_changed(database_relation), state=state)

    # THEN litmus auth server pebble plan is generated with extra db env vars
    backend_container_out = state_out.get_container(authserver_container.name)
    actual_env_vars = backend_container_out.plan.to_dict()["services"]["authserver"][
        "environment"
    ]
    assert expected_env_vars.issubset(actual_env_vars.keys())

    # AND the pebble service is running
    assert backend_container_out.services.get("authserver").is_running()
