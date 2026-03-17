# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from types import SimpleNamespace
from environment_manager import EnvironmentManager
from litmus_client import DEFAULT_ENVIRONMENT_ID

from conftest import MOCK_LITMUS_PROJECT_ID


def test_reconcile_creates_new_environment(mock_litmus_client):
    """GIVEN no Litmus envs exist, WHEN reconciling, THEN default env is created."""
    # GIVEN
    mock_litmus_client.list_environments.return_value = []
    manager = EnvironmentManager()

    # WHEN
    manager.reconcile(mock_litmus_client)

    # THEN
    mock_litmus_client.create_environment.assert_called_once_with(
        project_id=MOCK_LITMUS_PROJECT_ID,
        name=DEFAULT_ENVIRONMENT_ID,
    )


def test_reconcile_skips_environment_creation_if_it_already_exists(mock_litmus_client):
    """GIVEN a default env exists in the project, WHEN reconciling, THEN no actions are taken."""
    # GIVEN
    mock_litmus_client.list_environments.return_value = [
        SimpleNamespace(id="env-1", name=DEFAULT_ENVIRONMENT_ID)
    ]
    manager = EnvironmentManager()

    # WHEN
    manager.reconcile(mock_litmus_client)

    # THEN
    mock_litmus_client.create_environment.assert_not_called()
