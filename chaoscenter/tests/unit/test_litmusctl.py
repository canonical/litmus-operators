# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for litmusctl.Litmusctl."""

from unittest.mock import MagicMock

import ops
import ops.pebble
import pytest

from litmusctl import Litmusctl, LitmusctlError, LITMUSCTL_ENDPOINT


def _make_litmusctl(stdout: str = "", exit_code: int = 0) -> tuple[Litmusctl, MagicMock]:
    """Return a Litmusctl wired to a mock container.

    The mock container's exec() returns a process whose wait_output() either
    returns (stdout, "") or raises ExecError when exit_code != 0.
    """
    container = MagicMock(spec=ops.Container)
    proc = MagicMock()
    if exit_code != 0:
        proc.wait_output.side_effect = ops.pebble.ExecError(
            command=["litmusctl"],
            exit_code=exit_code,
            stdout="",
            stderr="something went wrong",
        )
    else:
        proc.wait_output.return_value = (stdout, "")
    container.exec.return_value = proc
    return Litmusctl(container), container


class TestRun:
    """Tests for the _run core method."""

    def test_exec_called_with_litmusctl_prefix(self):
        lctl, container = _make_litmusctl()
        lctl._run(["get", "projects"])
        container.exec.assert_called_once_with(["litmusctl", "get", "projects"])

    def test_returns_stdout(self):
        lctl, _ = _make_litmusctl(stdout="some output")
        assert lctl._run(["get", "projects"]) == "some output"

    def test_raises_litmusctl_error_on_nonzero_exit(self):
        lctl, _ = _make_litmusctl(exit_code=1)
        with pytest.raises(LitmusctlError):
            lctl._run(["get", "projects"])

    def test_litmusctl_error_contains_exit_code_and_stderr(self):
        lctl, _ = _make_litmusctl(exit_code=2)
        with pytest.raises(LitmusctlError, match="exit 2"):
            lctl._run(["get", "projects"])


class TestConfig:
    """Tests for config_* methods."""

    def test_set_account_uses_hardcoded_endpoint(self):
        lctl, container = _make_litmusctl()
        lctl.set_account(username="admin", password="s3cr3t")
        container.exec.assert_called_once_with([
            "litmusctl", "config", "set-account",
            "--endpoint", LITMUSCTL_ENDPOINT,
            "--username", "admin",
            "--password", "s3cr3t",
            "--non-interactive",
        ])

    def test_config_set_account(self):
        lctl, container = _make_litmusctl()
        lctl.config_set_account(endpoint="http://chaos:9091", username="admin", password="s3cr3t")
        container.exec.assert_called_once_with([
            "litmusctl", "config", "set-account",
            "--endpoint", "http://chaos:9091",
            "--username", "admin",
            "--password", "s3cr3t",
            "--non-interactive",
        ])

    def test_config_get_accounts_returns_output(self):
        lctl, _ = _make_litmusctl(stdout="CURRENT   ENDPOINT\n* http://chaos:9091")
        result = lctl.config_get_accounts()
        assert "http://chaos:9091" in result

    def test_config_get_accounts_calls_correct_command(self):
        lctl, container = _make_litmusctl()
        lctl.config_get_accounts()
        container.exec.assert_called_once_with(["litmusctl", "config", "get-accounts"])

    def test_config_view_calls_correct_command(self):
        lctl, container = _make_litmusctl()
        lctl.config_view()
        container.exec.assert_called_once_with(["litmusctl", "config", "view"])


class TestGet:
    """Tests for get_* methods."""

    def test_get_projects(self):
        lctl, container = _make_litmusctl()
        lctl.get_projects()
        container.exec.assert_called_once_with(["litmusctl", "get", "projects"])

    def test_get_chaos_infra(self):
        lctl, container = _make_litmusctl()
        lctl.get_chaos_infra(project_id="proj-1")
        container.exec.assert_called_once_with(
            ["litmusctl", "get", "chaos-infra", "--project-id", "proj-1"]
        )

    def test_get_chaos_environments_without_environment_id(self):
        lctl, container = _make_litmusctl()
        lctl.get_chaos_environments(project_id="proj-1")
        container.exec.assert_called_once_with(
            ["litmusctl", "get", "chaos-environments", "--project-id", "proj-1"]
        )

    def test_get_chaos_environments_with_environment_id(self):
        lctl, container = _make_litmusctl()
        lctl.get_chaos_environments(project_id="proj-1", environment_id="env-42")
        container.exec.assert_called_once_with([
            "litmusctl", "get", "chaos-environments",
            "--project-id", "proj-1",
            "--environment-id", "env-42",
        ])

    def test_get_returns_stdout(self):
        lctl, _ = _make_litmusctl(stdout="project-output")
        assert lctl.get_projects() == "project-output"


class TestCreate:
    """Tests for create_* methods."""

    def test_create_project(self):
        lctl, container = _make_litmusctl()
        lctl.create_project(name="my-project")
        container.exec.assert_called_once_with(
            ["litmusctl", "create", "project", "--name", "my-project"]
        )

    def test_create_chaos_environment(self):
        lctl, container = _make_litmusctl()
        lctl.create_chaos_environment(project_id="proj-1", name="my-env")
        container.exec.assert_called_once_with([
            "litmusctl", "create", "chaos-environment",
            "--project-id", "proj-1",
            "--name", "my-env",
        ])

    def test_create_returns_stdout(self):
        lctl, _ = _make_litmusctl(stdout="created project-id: proj-1")
        result = lctl.create_project(name="my-project")
        assert result == "created project-id: proj-1"


class TestDelete:
    """Tests for delete_* methods."""

    def test_delete_chaos_environment(self):
        lctl, container = _make_litmusctl()
        lctl.delete_chaos_environment(project_id="proj-1", environment_id="env-42")
        container.exec.assert_called_once_with([
            "litmusctl", "delete", "chaos-environment",
            "--project-id", "proj-1",
            "--environment-id", "env-42",
        ])

    def test_delete_raises_on_failure(self):
        lctl, _ = _make_litmusctl(exit_code=1)
        with pytest.raises(LitmusctlError):
            lctl.delete_chaos_environment(project_id="proj-1", environment_id="env-42")
