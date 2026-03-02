# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Thin wrapper around the litmusctl CLI, executed inside the workload container."""

import logging
from typing import List, Optional

import ops
import ops.pebble

logger = logging.getLogger(__name__)

LITMUSCTL_BIN = "litmusctl"
# The ChaosCenter frontend (nginx) is always reachable at this address from within the container.
LITMUSCTL_ENDPOINT = f"http://localhost:8185"


class LitmusctlError(Exception):
    """Raised when litmusctl exits with a non-zero status code."""


class Litmusctl:
    """Wrapper for the litmusctl CLI tool running inside an ops Container."""

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

    def set_account(self, username: str, password: str) -> None:
        """Register an account for the local ChaosCenter instance (litmusctl config set-account).

        Uses the hardcoded local endpoint since the charm always manages a single
        ChaosCenter instance running in the same container.
        """
        self.config_set_account(
            endpoint=LITMUSCTL_ENDPOINT,
            username=username,
            password=password,
        )

    def config_set_account(self, endpoint: str, username: str, password: str) -> None:
        """Register a ChaosCenter account (litmusctl config set-account)."""
        self._run([
            "config", "set-account",
            "--endpoint", endpoint,
            "--username", username,
            "--password", password,
            "--non-interactive",
        ])

    def config_get_accounts(self) -> str:
        """Return accounts defined in the litmusconfig (litmusctl config get-accounts)."""
        return self._run(["config", "get-accounts"])

    def config_view(self) -> str:
        """Return the raw litmusconfig contents (litmusctl config view)."""
        return self._run(["config", "view"])

    def get_projects(self) -> str:
        """List all projects accessible to the current account (litmusctl get projects)."""
        return self._run(["get", "projects"])

    def get_chaos_infra(self, project_id: str) -> str:
        """List Chaos Infrastructures within a project (litmusctl get chaos-infra)."""
        return self._run(["get", "chaos-infra", "--project-id", project_id])

    def get_chaos_environments(self, project_id: str, environment_id: Optional[str] = None) -> str:
        """List Chaos Environments within a project (litmusctl get chaos-environments).

        Pass environment_id to narrow the result to a single environment.
        """
        args = ["get", "chaos-environments", "--project-id", project_id]
        if environment_id:
            args += ["--environment-id", environment_id]
        return self._run(args)

    def create_project(self, name: str) -> str:
        """Create a project (litmusctl create project)."""
        return self._run(["create", "project", "--name", name])

    def create_chaos_environment(self, project_id: str, name: str) -> str:
        """Create a Chaos Environment (litmusctl create chaos-environment)."""
        return self._run([
            "create", "chaos-environment",
            "--project-id", project_id,
            "--name", name,
        ])

    def delete_chaos_environment(self, project_id: str, environment_id: str) -> None:
        """Delete a Chaos Environment (litmusctl delete chaos-environment)."""
        self._run([
            "delete", "chaos-environment",
            "--project-id", project_id,
            "--environment-id", environment_id,
        ])
