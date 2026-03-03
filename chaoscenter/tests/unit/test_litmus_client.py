# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for litmusctl.Litmusctl."""

import json
from unittest.mock import MagicMock

import ops
import ops.pebble
import pytest

from litmus_client import LitmusClient, LitmusctlError, ChaosProject

MOCK_ENDPOINT = "http://chaos:9091"


def _make_litmus_client(
    stdout: str = "", exit_code: int = 0
) -> tuple[LitmusClient, MagicMock]:
    """Return a LitmusClient wired to a mock container.

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
    return LitmusClient(container, MOCK_ENDPOINT), container


class TestRun:
    """Tests for the _run core method (via the internal _cli)."""

    def test_exec_called_with_litmusctl_prefix(self):
        lctl, container = _make_litmus_client()
        # Testing the underlying run logic
        lctl._cli._run(["get", "projects"])
        container.exec.assert_called_once_with(["litmusctl", "get", "projects"])

    def test_returns_stdout(self):
        lctl, _ = _make_litmus_client(stdout="some output")
        assert lctl._cli._run(["get", "projects"]) == "some output"

    def test_raises_litmusctl_error_on_nonzero_exit(self):
        lctl, _ = _make_litmus_client(exit_code=1)
        with pytest.raises(LitmusctlError):
            lctl._cli._run(["get", "projects"])

    def test_litmusctl_error_contains_exit_code_and_stderr(self):
        lctl, _ = _make_litmus_client(exit_code=2)
        with pytest.raises(LitmusctlError, match="exit 2"):
            lctl._cli._run(["get", "projects"])


class TestConfig:
    """Tests for config methods."""

    def test_config_set_account_uses_provided_endpoint(self):
        lctl, container = _make_litmus_client()
        lctl.config_set_account(username="admin", password="s3cr3t")
        container.exec.assert_called_once_with(
            [
                "litmusctl",
                "config",
                "set-account",
                "--endpoint",
                MOCK_ENDPOINT,
                "--username",
                "admin",
                "--password",
                "s3cr3t",
                "--non-interactive",
            ]
        )


class TestGet:
    """Tests for get_* methods."""

    def test_get_projects_calls_correct_command(self):
        # We need a valid JSON string for the new client to parse
        mock_json = json.dumps({"projects": []})
        lctl, container = _make_litmus_client(stdout=mock_json)
        lctl.get_projects()
        container.exec.assert_called_once_with(
            ["litmusctl", "get", "projects", "--output", "json"]
        )

    def test_get_projects_returns_dataclasses(self):
        mock_json = json.dumps(
            {"projects": [{"projectID": "proj-123", "name": "Test Project"}]}
        )
        lctl, _ = _make_litmus_client(stdout=mock_json)
        result = lctl.get_projects()

        assert len(result) == 1
        assert isinstance(result[0], ChaosProject)
        assert result[0].id == "proj-123"
        assert result[0].name == "Test Project"


class TestCreate:
    """Tests for create_* methods."""

    def test_create_chaos_environment(self):
        lctl, container = _make_litmus_client()
        lctl.create_chaos_environment(project_id="proj-1", name="my-env")
        container.exec.assert_called_once_with(
            [
                "litmusctl",
                "create",
                "chaos-environment",
                "--project-id",
                "proj-1",
                "--name",
                "my-env",
            ]
        )

    def test_create_returns_stdout(self):
        lctl, _ = _make_litmus_client(stdout="successfully created")
        result = lctl.create_chaos_environment(project_id="proj-1", name="my-env")
        assert result == "successfully created"
