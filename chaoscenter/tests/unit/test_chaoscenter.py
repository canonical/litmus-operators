# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Scenario (state-transition) tests for Chaoscenter user-credential management."""

from unittest.mock import patch

import ops
import pytest
import requests_mock as requests_mock_module
from ops.testing import CharmEvents, State

BASE_URL = "http://litmus.local:8185"
AUTH_URL = f"{BASE_URL}/auth/login"
USERS_URL = f"{BASE_URL}/auth/users"
CREATE_URL = f"{BASE_URL}/auth/create_user"
UPDATE_PASSWORD_URL = f"{BASE_URL}/auth/update/password"


@pytest.fixture(autouse=True)
def _patch_cc_url():
    with patch(
        "charm.LitmusChaoscenterCharm._internal_frontend_url", "http://litmus.local"
    ):
        yield


@pytest.fixture(autouse=True)
def _patch_env_reconciler():
    with patch("environment_manager.EnvironmentManager.reconcile"):
        yield


@pytest.fixture(autouse=True)
def _patch_infra_reconciler():
    with patch("infra_manager.InfraManager.reconcile"):
        yield


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

    # THEN the unit is blocked with a message referencing user_secrets
    assert isinstance(state_out.unit_status, ops.BlockedStatus)
    assert "user_secrets" in state_out.unit_status.message


# ---------------------------------------------------------------------------
# Test 1b – user_secrets config set but secret contains invalid data → BlockedStatus
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "event",
    [
        CharmEvents.config_changed(),
        CharmEvents.install(),
        CharmEvents.update_status(),
    ],
)
def test_invalid_user_secrets_sets_blocked_status(
    ctx,
    nginx_container,
    nginx_prometheus_exporter_container,
    event,
):
    # GIVEN the charm has 'user_secrets' config pointing to a secret with invalid passwords
    invalid_secret = ops.testing.Secret(
        tracked_content={"admin-password": "tooshort", "charm-password": "Charm1!pass"}
    )
    state = State(
        containers=[nginx_container, nginx_prometheus_exporter_container],
        config={"user_secrets": invalid_secret.id},
        secrets=[invalid_secret],
    )

    # WHEN any event fires
    state_out = ctx.run(event, state=state)

    # THEN the unit is blocked with a message indicating the secret is not valid
    assert isinstance(state_out.unit_status, ops.BlockedStatus)
    assert "not valid" in state_out.unit_status.message


# ---------------------------------------------------------------------------
# Test 2 – valid credentials → Litmus API calls are made correctly
# ---------------------------------------------------------------------------


def test_valid_credentials_calls_litmus_api(
    ctx,
    nginx_container,
    nginx_prometheus_exporter_container,
    auth_http_api_relation,
    backend_http_api_relation,
    user_secret,
    user_secrets_config,
):
    # GIVEN mocked Litmus API endpoints
    with requests_mock_module.Mocker() as m:
        # admin login with target password fails (first deployment)
        m.post(
            AUTH_URL,
            [
                {"status_code": 401},  # admin / target password – not yet set
                {
                    "json": {"accessToken": "tok"},
                    "status_code": 200,
                },  # admin / default password
                {
                    "json": {"accessToken": "tok"},
                    "status_code": 200,
                },  # admin login for user_exists
            ],
        )
        m.post(UPDATE_PASSWORD_URL, status_code=200, json={})
        m.get(USERS_URL, json=[])  # charm user does not exist yet
        m.post(CREATE_URL, status_code=200, json={})

        state = State(
            containers={nginx_container, nginx_prometheus_exporter_container},
            relations={auth_http_api_relation, backend_http_api_relation},
            config=user_secrets_config,
            secrets=[user_secret],
        )

        # WHEN any event fires
        ctx.run(ctx.on.config_changed(), state=state)

    # THEN the reset-password endpoint was called for admin
    assert any(r.url == UPDATE_PASSWORD_URL for r in m.request_history)
    # AND the create endpoint was called for the charm user
    assert any(r.url == CREATE_URL for r in m.request_history)
