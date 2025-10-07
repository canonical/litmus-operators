# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
from ops.testing import State
from dataclasses import replace

import pytest
from conftest import db_remote_databag, auth_remote_databag, patch_cert_and_key_ctx


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
    actual_env_vars = authserver_container_out.plan.to_dict()["services"]["auth"][
        "environment"
    ]
    assert actual_env_vars.keys() == expected_env_vars

    # AND the pebble service is NOT running
    assert not authserver_container_out.services.get("auth").is_running()


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
        remote_app_data=db_remote_databag(),
    )
    state = State(containers=[authserver_container], relations=[database_relation])

    # WHEN a relation changed event is fired
    state_out = ctx.run(ctx.on.relation_changed(database_relation), state=state)

    # THEN litmus auth server pebble plan is generated with an extra frontend env var
    auth_container_out = state_out.get_container(authserver_container.name)
    actual_env_vars = auth_container_out.plan.to_dict()["services"]["auth"][
        "environment"
    ]
    assert expected_env_vars.issubset(actual_env_vars.keys())

    # AND the pebble service is running
    assert auth_container_out.services.get("auth").is_running()


def test_pebble_plan_with_litmus_auth_relation(
    ctx, authserver_container, auth_relation
):
    expected_env_vars = {
        "LITMUS_GQL_GRPC_ENDPOINT",
        "LITMUS_GQL_GRPC_PORT",
    }
    # GIVEN a running container with a litmus-auth relation
    auth_relation = replace(
        auth_relation,
        remote_app_data=auth_remote_databag(),
    )
    state = State(containers=[authserver_container], relations=[auth_relation])

    # WHEN a relation changed event is fired
    state_out = ctx.run(ctx.on.relation_changed(auth_relation), state=state)

    # THEN litmus auth server pebble plan is generated with extra db env vars
    auth_container_out = state_out.get_container(authserver_container.name)
    actual_env_vars = auth_container_out.plan.to_dict()["services"]["auth"][
        "environment"
    ]
    assert expected_env_vars.issubset(actual_env_vars.keys())

    # AND the pebble service is NOT running
    assert not auth_container_out.services.get("auth").is_running()


def test_pebble_plan_with_tls_certificates_relation(
    ctx, authserver_container, tls_certificates_relation, patch_cert_and_key
):
    expected_env_vars = {
        "ENABLE_INTERNAL_TLS",
        "REST_PORT",
        "GRPC_PORT",
        "TLS_CERT_PATH",
        "TLS_KEY_PATH",
        "CA_CERT_TLS_PATH",
    }

    # GIVEN a running container with a tls-certificates relation
    state = State(
        containers=[authserver_container], relations=[tls_certificates_relation]
    )

    # WHEN a relation changed event is fired
    state_out = ctx.run(ctx.on.relation_changed(tls_certificates_relation), state=state)

    # THEN litmus auth server pebble plan is generated with extra TLS env vars
    authserver_container_out = state_out.get_container(authserver_container.name)
    actual_env_vars = authserver_container_out.plan.to_dict()["services"]["auth"][
        "environment"
    ]
    assert expected_env_vars.issubset(actual_env_vars.keys())

    # AND the pebble service is NOT running
    assert not authserver_container_out.services.get("auth").is_running()


def test_pebble_service_running(
    ctx, authserver_container, auth_relation, database_relation
):
    # GIVEN a running container with an auth and a database relation
    auth_relation = replace(
        auth_relation,
        remote_app_data=auth_remote_databag(),
    )
    database_relation = replace(
        database_relation,
        remote_app_data=db_remote_databag(),
    )
    state = State(
        containers=[authserver_container], relations=[auth_relation, database_relation]
    )

    # WHEN a relation changed event is fired
    state_out = ctx.run(ctx.on.relation_changed(auth_relation), state=state)

    # THEN litmus auth server pebble service is running
    auth_container_out = state_out.get_container(authserver_container.name)
    assert auth_container_out.services.get("auth").is_running()


@pytest.mark.parametrize("tls", (False, True))
def test_pebble_checks_plan(
    ctx, authserver_container, auth_relation, database_relation, tls, unit_fqdn
):
    # GIVEN a running container with an auth and a database relation
    auth_relation = replace(
        auth_relation,
        remote_app_data=auth_remote_databag(),
    )
    database_relation = replace(
        database_relation,
        remote_app_data=db_remote_databag(),
    )
    state = State(
        containers=[authserver_container], relations=[auth_relation, database_relation]
    )
    with patch_cert_and_key_ctx(tls):
        # WHEN a workload pebble ready event is fired
        state_out = ctx.run(ctx.on.relation_changed(auth_relation), state=state)

    # THEN litmus auth server pebble plan is generated with the correct pebble checks
    auth_container_out = state_out.get_container(authserver_container.name)
    assert auth_container_out.plan.checks["auth-up"].tcp == {
        "port": (3001 if tls else 3000)
    }
