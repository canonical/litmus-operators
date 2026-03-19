# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.


from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from infra_manager import InfraManager

import pytest

from environment_manager import DEFAULT_ENVIRONMENT
from conftest import MOCK_LITMUS_PROJECT_ID


@pytest.fixture
def mock_apply_k8s_manifest():
    with patch("infra_manager.InfraManager._apply_manifest") as mock:
        yield mock


def test_reconcile_creates_new_infrastructure(
    mock_litmus_client, mock_apply_k8s_manifest
):
    """GIVEN a desired infra that doesn't exist, WHEN reconciling, THEN it is registered and applied."""
    # GIVEN: Databag has one infra, but the backend is empty
    infra_data = [MagicMock(infrastructure_name="new-infra", model_name="test-ns")]
    mock_litmus_client.list_infrastructures.return_value = []
    mock_litmus_client.register_infrastructure.return_value = "generated-uuid"
    mock_litmus_client.get_infrastructure_manifest.return_value = "yaml-content"

    manager = InfraManager(infra_data)

    # WHEN
    manager.reconcile(mock_litmus_client)

    # THEN
    mock_litmus_client.register_infrastructure.assert_called_once_with(
        "new-infra", "test-ns", MOCK_LITMUS_PROJECT_ID, DEFAULT_ENVIRONMENT
    )
    # Check that it tried to apply the manifest after registration
    mock_apply_k8s_manifest.assert_any_call("yaml-content")


def test_reconcile_skips_active_infrastructure(
    mock_litmus_client, mock_apply_k8s_manifest
):
    """GIVEN an infra that is already active, WHEN reconciling, THEN no actions are taken."""
    # GIVEN: Databag and backend match, and it's already active
    infra_data = [
        SimpleNamespace(infrastructure_name="k8s-infra", model_name="test-ns")
    ]
    mock_litmus_client.list_infrastructures.return_value = [
        SimpleNamespace(id="id-1", name="k8s-infra", namespace="test-ns", active=True)
    ]

    manager = InfraManager(infra_data)

    # WHEN
    manager.reconcile(mock_litmus_client)

    # THEN
    mock_litmus_client.register_infrastructure.assert_not_called()
    mock_apply_k8s_manifest.assert_not_called()


def test_reconcile_reactivates_inactive_infrastructure(
    mock_litmus_client, mock_apply_k8s_manifest
):
    """GIVEN an existing infra that is inactive, WHEN reconciling, THEN it is re-applied."""
    # GIVEN: Infra exists in backend but is NOT active
    infra_data = [
        SimpleNamespace(infrastructure_name="k8s-infra", model_name="test-ns")
    ]
    mock_litmus_client.list_infrastructures.return_value = [
        SimpleNamespace(id="id-1", name="k8s-infra", namespace="test-ns", active=False)
    ]
    mock_litmus_client.get_infrastructure_manifest.return_value = "re-apply-this"

    manager = InfraManager(infra_data)

    # WHEN
    manager.reconcile(mock_litmus_client)

    # THEN: No new registration, but manifest is fetched and applied
    mock_litmus_client.register_infrastructure.assert_not_called()
    mock_litmus_client.get_infrastructure_manifest.assert_called_with(
        "id-1", MOCK_LITMUS_PROJECT_ID
    )
    mock_apply_k8s_manifest.assert_any_call("re-apply-this")


def test_reconcile_deletes_removed_infrastructure(mock_litmus_client):
    """GIVEN an infra in the backend not in desired state, WHEN reconciling, THEN it is deleted."""
    # GIVEN: Databag is empty, but backend has an infra
    infra_data = []
    mock_litmus_client.list_infrastructures.return_value = [
        SimpleNamespace(id="old-uuid", name="stale-infra", namespace="old-ns")
    ]

    manager = InfraManager(infra_data)

    # WHEN
    manager.reconcile(mock_litmus_client)

    # THEN
    mock_litmus_client.delete_infrastructure.assert_called_once_with(
        "old-uuid", MOCK_LITMUS_PROJECT_ID
    )
