# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
"""This module contains methods, responsible for creating a default environment in Chaoscenter."""

import logging

from litmus_client import DEFAULT_ENVIRONMENT_ID, LitmusClient

logger = logging.getLogger(__name__)


def reconcile(litmus_client: LitmusClient) -> None:
    """Reconcile the state of the environment, ensuring that it is in the desired state."""
    default_project_id = litmus_client.get_default_project_id()
    if not _environment_exists(
        litmus_client, default_project_id, DEFAULT_ENVIRONMENT_ID
    ):
        litmus_client.create_environment(
            project_id=default_project_id, name=DEFAULT_ENVIRONMENT_ID
        )
        logger.info(f"Default environment {DEFAULT_ENVIRONMENT_ID} created")


def _environment_exists(
    litmus_client: LitmusClient,
    project_id: str,
    env_name: str,
) -> bool:
    return any(
        env.name == env_name for env in litmus_client.list_environments(project_id)
    )
