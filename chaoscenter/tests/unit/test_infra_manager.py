# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.


from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call
from infra_manager import InfraManager

import pytest

from environment_manager import DEFAULT_ENVIRONMENT
from conftest import MOCK_LITMUS_PROJECT_ID


@pytest.fixture
def mock_apply_k8s_manifest():
    with patch("infra_manager.InfraManager._apply_manifest") as mock:
        yield mock


@pytest.fixture
def mock_delete_k8s_manifest():
    with patch("infra_manager.InfraManager._delete_manifest") as mock:
        yield mock


@pytest.fixture
def mock_delete_k8s_experiments():
    with patch("infra_manager.InfraManager._delete_chaos_experiments_from_k8s") as mock:
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


def test_reconcile_deletes_removed_infrastructure(
    mock_litmus_client, mock_delete_k8s_manifest, mock_delete_k8s_experiments
):
    """GIVEN an infra in the backend not in desired state, WHEN reconciling, THEN it is deleted."""
    # GIVEN: Databag is empty, but backend has an infra
    infra_data = []
    mock_litmus_client.list_infrastructures.return_value = [
        SimpleNamespace(id="old-uuid", name="stale-infra", namespace="old-ns")
    ]
    mock_litmus_client.get_infrastructure_manifest.return_value = "re-apply-this"

    manager = InfraManager(infra_data)

    # WHEN
    manager.reconcile(mock_litmus_client)

    # THEN
    mock_litmus_client.delete_infrastructure.assert_called_once_with(
        "old-uuid", MOCK_LITMUS_PROJECT_ID
    )
    mock_delete_k8s_manifest.assert_any_call("re-apply-this")
    mock_delete_k8s_experiments.assert_any_call(namespace="old-ns")


def test_reconcile_deletes_removed_infrastructure_experiments(
    mock_litmus_client, mock_delete_k8s_manifest, mock_delete_k8s_experiments
):
    """GIVEN an infra in the backend not in desired state, WHEN reconciling, THEN associated chaos experiments are deleted."""
    # GIVEN: Databag is empty, but backend has an infra
    infra_data = []
    mock_litmus_client.list_infrastructures.return_value = [
        SimpleNamespace(id="old-uuid", name="stale-infra", namespace="old-ns")
    ]
    mock_litmus_client.list_experiments.return_value = [
        SimpleNamespace(id="exp-1", infra_id="old-uuid"),
        SimpleNamespace(id="exp-2", infra_id="old-uuid"),
        SimpleNamespace(id="exp-3", infra_id="other-infra"),
    ]

    manager = InfraManager(infra_data)

    # WHEN
    manager.reconcile(mock_litmus_client)

    # THEN
    mock_litmus_client.delete_experiment.assert_any_call(
        project_id=MOCK_LITMUS_PROJECT_ID, experiment_id="exp-1"
    )
    mock_litmus_client.delete_experiment.assert_any_call(
        project_id=MOCK_LITMUS_PROJECT_ID, experiment_id="exp-2"
    )
    assert (
        call(project_id=MOCK_LITMUS_PROJECT_ID, experiment_id="exp-3")
        not in mock_litmus_client.delete_experiment.mock_calls
    )
