# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""High-level client for interacting with the Litmus API and CLI (litmusctl)."""

from dataclasses import dataclass
import json
import logging
from typing import List

import ops
import ops.pebble

logger = logging.getLogger(__name__)

LITMUSCTL_BIN = "litmusctl"
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "litmus"


@dataclass
class ChaosInfra:
    id: str
    name: str
    project_id: str
    environment_id: str


@dataclass
class ChaosProject:
    id: str
    name: str


class LitmusctlError(Exception):
    """Raised when litmusctl exits with a non-zero status code."""


class _LitmusCLI:
    """Low-level wrapper around litmusctl CLI commands."""

    def __init__(self, container: ops.Container):
        self._container = container

    def _run(self, args: List[str]) -> str:
        """Run litmusctl with the given arguments.

        Returns stdout output.
        Raises LitmusctlError if the process exits with a non-zero status.
        """

        cmd = [LITMUSCTL_BIN] + args
        logger.debug("running: %s", " ".join(cmd))
        try:
            proc = self._container.exec(cmd)
            stdout, _ = proc.wait_output()
        except ops.pebble.ExecError as e:
            raise LitmusctlError(
                f"litmusctl command failed (exit {e.exit_code}): {' '.join(args)}\n"
                f"stderr: {e.stderr}"
            ) from e
        return stdout

    def config_set_account(self, endpoint: str, username: str, password: str) -> None:
        self._run(
            [
                "config",
                "set-account",
                "--endpoint",
                endpoint,
                "--username",
                username,
                "--password",
                password,
                "--non-interactive",
            ]
        )

    def get_projects(self) -> list[ChaosProject]:
        out = json.loads(self._run(["get", "projects", "--output", "json"]))
        return [
            ChaosProject(id=item["projectID"], name=item["name"])
            for item in out.get("projects", [])
        ]

    def create_chaos_environment(self, project_id: str, name: str) -> None:
        return self._run(
            [
                "create",
                "chaos-environment",
                "--project-id",
                project_id,
                "--name",
                name,
            ]
        )


class LitmusClient:
    """High-level Litmus client.

    Some operations use the CLI (litmusctl).
    others use the API when CLI support is missing.
    """

    def __init__(self, container: ops.Container, endpoint: str):
        self._container = container
        self._endpoint = endpoint
        self._cli = _LitmusCLI(container)
        # TODO: implement a _LitmusAPI class for direct API calls when needed, and initialize it here
        # self._api = _LitmusAPI()

    def config_set_account(self, username: str, password: str) -> None:
        """Register a ChaosCenter account and initialize session tokens (litmusctl config set-account)."""
        self._cli.config_set_account(self._endpoint, username, password)

    def get_projects(self) -> list[ChaosProject]:
        """List all projects accessible to the current account (litmusctl get projects)."""
        return self._cli.get_projects()

    def create_chaos_environment(self, project_id: str, name: str) -> str:
        """Create a Chaos Environment (litmusctl create chaos-environment)."""
        return self._cli.create_chaos_environment(project_id, name)
