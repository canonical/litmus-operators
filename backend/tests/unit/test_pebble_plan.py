# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
from ops.testing import State
from dataclasses import replace
from conftest import db_remote_databag, auth_remote_databag


def test_pebble_plan_minimal(ctx, backend_container):
    expected_env_vars = {
        "REST_PORT",
        "GRPC_PORT",
        "INFRA_DEPLOYMENTS",
        "DEFAULT_HUB_BRANCH_NAME",
        "ALLOWED_ORIGINS",
        "CONTAINER_RUNTIME_EXECUTOR",
        "WORKFLOW_HELPER_IMAGE_VERSION",
        "INFRA_COMPATIBLE_VERSIONS",
        "VERSION",
        "SUBSCRIBER_IMAGE",
        "EVENT_TRACKER_IMAGE",
        "ARGO_WORKFLOW_CONTROLLER_IMAGE",
        "ARGO_WORKFLOW_EXECUTOR_IMAGE",
        "LITMUS_CHAOS_OPERATOR_IMAGE",
        "LITMUS_CHAOS_RUNNER_IMAGE",
        "LITMUS_CHAOS_EXPORTER_IMAGE",
    }

    # GIVEN a running container with no relations
    state = State(containers=[backend_container], relations=[])

    # WHEN a workload pebble ready event is fired
    state_out = ctx.run(ctx.on.pebble_ready(backend_container), state=state)

    # THEN litmus backend server pebble plan is generated with the right env vars
    backend_container_out = state_out.get_container(backend_container.name)
    actual_env_vars = backend_container_out.plan.to_dict()["services"][
        "litmuschaos-server"
    ]["environment"]
    assert actual_env_vars.keys() == expected_env_vars

    # AND the pebble service is NOT running
    assert not backend_container_out.services.get("litmuschaos-server").is_running()


def test_pebble_plan_with_database_relation(ctx, backend_container, database_relation):
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
    state = State(containers=[backend_container], relations=[database_relation])

    # WHEN a relation changed event is fired
    state_out = ctx.run(ctx.on.relation_changed(database_relation), state=state)

    # THEN litmus backend server pebble plan is generated with extra db env vars
    backend_container_out = state_out.get_container(backend_container.name)
    actual_env_vars = backend_container_out.plan.to_dict()["services"][
        "litmuschaos-server"
    ]["environment"]
    assert expected_env_vars.issubset(actual_env_vars.keys())

    # AND the pebble service is running
    assert backend_container_out.services.get("litmuschaos-server").is_running()


def test_pebble_plan_with_auth_relation(ctx, backend_container, auth_relation):
    expected_env_vars = {
        "LITMUS_AUTH_GRPC_ENDPOINT",
        "LITMUS_AUTH_GRPC_PORT",
    }
    # GIVEN a running container with an auth relation
    auth_relation = replace(
        auth_relation,
        remote_app_data=auth_remote_databag(),
    )
    state = State(containers=[backend_container], relations=[auth_relation])

    # WHEN a relation changed event is fired
    state_out = ctx.run(ctx.on.relation_changed(auth_relation), state=state)

    # THEN litmus backend server pebble plan is generated with extra db env vars
    backend_container_out = state_out.get_container(backend_container.name)
    actual_env_vars = backend_container_out.plan.to_dict()["services"][
        "litmuschaos-server"
    ]["environment"]
    assert expected_env_vars.issubset(actual_env_vars.keys())

    # AND the pebble service is NOT running
    assert not backend_container_out.services.get("litmuschaos-server").is_running()


def test_pebble_service_running(
    ctx, backend_container, auth_relation, database_relation
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
        containers=[backend_container], relations=[auth_relation, database_relation]
    )

    # WHEN a relation changed event is fired
    state_out = ctx.run(ctx.on.relation_changed(auth_relation), state=state)

    # THEN litmus backend server pebble service is running
    backend_container_out = state_out.get_container(backend_container.name)
    assert backend_container_out.services.get("litmuschaos-server").is_running()
