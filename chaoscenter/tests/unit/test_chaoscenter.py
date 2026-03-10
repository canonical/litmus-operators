# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Scenario (state-transition) tests for Chaoscenter user-credential management."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import ops
import pytest
import requests_mock as requests_mock_module
from ops.testing import CharmEvents, State
from litmus_client import ChaosInfrastructure
from chaoscenter import Chaoscenter

BASE_URL = "http://litmus.local:8185"
AUTH_URL = f"{BASE_URL}/auth/login"
USERS_URL = f"{BASE_URL}/auth/users"
CREATE_URL = f"{BASE_URL}/auth/create_user"
UPDATE_PASSWORD_URL = f"{BASE_URL}/auth/update/password"
MOCK_PROJECT_ID = "default_project_id"


@pytest.fixture(autouse=True)
def _patch_cc_url():
    with patch(
        "charm.LitmusChaoscenterCharm._internal_frontend_url", "http://litmus.local"
    ):
        yield


@pytest.fixture()
def patch_apply_manifests():
    with patch("chaoscenter.Chaoscenter._apply_manifest") as mock_apply:
        yield mock_apply


@pytest.fixture
def patch_crd_mainfests_path(tmp_path):
    mock_crd_file = Path(tmp_path / "sample_crd.yaml")
    mock_crd_file.write_text("apiVersion: v1\nkind: SampleCRD")
    with patch("chaoscenter.LITMUS_CRD_MANIFEST_PATH", mock_crd_file):
        yield mock_crd_file


@pytest.fixture
def mock_litmus_client():
    mock = MagicMock()
    mock.return_value.default_project_id = MOCK_PROJECT_ID
    return mock


@pytest.fixture
def mock_infra_data():
    return SimpleNamespace(
        infrastructure_name="k8s-infra",
        model_name="prod-model",
    )


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


def test_infrastructure_creation(
    mock_litmus_client,
    mock_infra_data,
    patch_crd_mainfests_path,
    patch_apply_manifests,
):
    """Verifies that the charm registers and applies infrastructure when it doesn't exist."""

    cc = Chaoscenter("http://litmus.local", None, None)

    with patch("user_manager.UserManager.get_charm_client", mock_litmus_client):
        # GIVEN no existing infrastructure in the backend
        mock_litmus_client.return_value.get_infrastructure.return_value = None
        mock_litmus_client.return_value.register_infrastructure.return_value = (
            "kind: Deployment\nname: agent"
        )

        # WHEN the charm tries to create the infrastructure
        cc.create_infrastructure(mock_infra_data)

        # THEN the charm should register the infrastructure
        mock_litmus_client.return_value.register_infrastructure.assert_called_once_with(
            "k8s-infra", "prod-model", MOCK_PROJECT_ID
        )

        # AND the charm should apply both the CRDs and the newly generated manifest
        assert patch_apply_manifests.call_count == 2
        patch_apply_manifests.assert_any_call(patch_crd_mainfests_path.read_text())
        patch_apply_manifests.assert_any_call("kind: Deployment\nname: agent")


def test_infrastructure_skipped_if_already_active(
    mock_litmus_client,
    patch_apply_manifests,
    mock_infra_data,
):
    """Verifies idempotency: skip registration if infrastructure is already active."""

    cc = Chaoscenter("http://litmus.local", None, None)

    # GIVEN the infrastructure already exists and is active
    mock_litmus_client.return_value.get_infrastructure.return_value = (
        ChaosInfrastructure(
            id="infra-123", name="k8s-infra", environment_id="test", active=True
        )
    )

    with patch("user_manager.UserManager.get_charm_client", mock_litmus_client):
        # WHEN the charm tries to create the infrastructure
        cc.create_infrastructure(mock_infra_data)
        # THEN registration is skipped and nothing is applied
        mock_litmus_client.return_value.register_infrastructure.assert_not_called()
        patch_apply_manifests.assert_not_called()


def test_infrastructure_reapplied_if_inactive(
    mock_litmus_client,
    patch_apply_manifests,
    mock_infra_data,
):
    """Verifies that we re-fetch and apply the manifest if the infra is inactive."""
    cc = Chaoscenter("http://litmus.local", None, None)

    # GIVEN infrastructure exists but is NOT active
    mock_litmus_client.return_value.get_infrastructure.return_value = (
        ChaosInfrastructure(
            id="infra-123", name="k8s-infra", environment_id="test", active=False
        )
    )
    mock_litmus_client.return_value.get_infrastructure_manifest.return_value = (
        "re-apply-this-yaml"
    )

    with (
        patch("user_manager.UserManager.get_charm_client", mock_litmus_client),
    ):
        # WHEN the charm tries to create the infrastructure
        cc.create_infrastructure(mock_infra_data)
        # THEN we fetch the manifest for the existing ID
        mock_litmus_client.return_value.get_infrastructure_manifest.assert_called_once_with(
            "infra-123", MOCK_PROJECT_ID
        )
        # AND apply it
        patch_apply_manifests.assert_any_call("re-apply-this-yaml")


def test_infrastructure_deletion(
    mock_litmus_client,
    mock_infra_data,
):
    """Verifies that infrastructure is deleted from the backend when the relation is departing."""
    cc = Chaoscenter("http://litmus.local", None, None)

    # GIVEN infrastructure exists
    mock_litmus_client.return_value.get_infrastructure.return_value = (
        ChaosInfrastructure(
            id="infra-uuid", name="k8s-infra", environment_id="test", active=True
        )
    )

    with (
        patch("user_manager.UserManager.get_charm_client", mock_litmus_client),
    ):
        # WHEN the charm tries to delete the infrastructure
        cc.delete_infrastructure(mock_infra_data)

        # THEN the client should be called to delete the specific infrastructure
        mock_litmus_client.return_value.delete_infrastructure.assert_called_once_with(
            "infra-uuid", MOCK_PROJECT_ID
        )
