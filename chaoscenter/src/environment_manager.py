# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
"""This module contains the EnvironmentManager class, which is responsible for creating a default environment in Chaoscenter."""

from litmus_client import LitmusClient

CHARM_ENV_NAME = "charmed_litmus"


class EnvironmentManager:
    def reconcile(self, litmus_client: LitmusClient) -> None:
        """Reconcile the state of the environment, ensuring that it is in the desired state."""
        default_project_id = litmus_client.get_default_project_id()
        if not self._environment_exists(litmus_client, default_project_id, CHARM_ENV_NAME):
            litmus_client.create_environment(project_id=default_project_id, name=CHARM_ENV_NAME)

    @staticmethod
    def _environment_exists(
            litmus_client: LitmusClient,
            project_id: str,
            env_name: str,
    ) -> bool:
        return any(
            env.name == env_name
            for env in litmus_client.list_environments(project_id)
        )
