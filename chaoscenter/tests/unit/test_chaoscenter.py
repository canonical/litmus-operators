# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Scenario (state-transition) tests for Chaoscenter user-credential management."""

from dataclasses import replace

import ops
import pytest
from ops.testing import CharmEvents, Exec, State

from litmusctl import LITMUSCTL_ENDPOINT


# ---------------------------------------------------------------------------
# Test 1 – missing user_secrets config → BlockedStatus
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "event",
    [
        CharmEvents.config_changed(),
        CharmEvents.install(),
        CharmEvents.update_status(),
    ],
)
def test_missing_user_secrets_sets_blocked_status(
    ctx,
    nginx_container,
    nginx_prometheus_exporter_container,
    event,
):
    # GIVEN the charm has no 'user_secrets' config option set
    state = State(
        containers=[nginx_container, nginx_prometheus_exporter_container],
    )

    # WHEN any event fires
    state_out = ctx.run(event, state=state)

    # THEN the unit is blocked
    assert isinstance(state_out.unit_status, ops.BlockedStatus)
    assert "user_secrets" in state_out.unit_status.message


# ---------------------------------------------------------------------------
# Test 2 – valid credentials → litmusctl set-account calls are made
# ---------------------------------------------------------------------------


def test_valid_credentials_calls_litmusctl_set_account(
    ctx,
    nginx_container,
    nginx_prometheus_exporter_container,
    auth_http_api_relation,
    backend_http_api_relation,
    user_secret,
    user_secrets_config,
):
    # GIVEN a container with Exec mocks for the expected litmusctl calls
    container = replace(
        nginx_container,
        execs={
            Exec(["update-ca-certificates", "--fresh"], return_code=0),
            Exec(["litmusctl", "config", "set-account"], return_code=0),
        },
    )
    state = State(
        containers={container, nginx_prometheus_exporter_container},
        relations={auth_http_api_relation, backend_http_api_relation},
        config=user_secrets_config,
        secrets=[user_secret],
    )

    # WHEN any event fires
    ctx.run(ctx.on.config_changed(), state=state)

    # THEN litmusctl config set-account is called for the admin account
    exec_commands = [args.command for args in ctx.exec_history.get("chaoscenter", [])]
    assert [
        "litmusctl", "config", "set-account",
        "--endpoint", LITMUSCTL_ENDPOINT,
        "--username", "admin",
        "--password", "admin123",
        "--non-interactive",
    ] in exec_commands

    # AND for the charm bot account
    assert [
        "litmusctl", "config", "set-account",
        "--endpoint", LITMUSCTL_ENDPOINT,
        "--username", "charm",
        "--password", "charm123",
        "--non-interactive",
    ] in exec_commands
