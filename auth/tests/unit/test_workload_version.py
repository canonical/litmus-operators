# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
from dataclasses import replace
from pathlib import Path
import pytest
from ops.testing import State, Mount


@pytest.fixture
def version_file(tmp_path: Path):
    file = tmp_path / "VERSION"
    file.write_text("fake_version")
    return file


@pytest.mark.parametrize("can_connect", (False, True))
def test_workload_version_unset(ctx, authserver_container, can_connect):
    # GIVEN a auth container with no mounted version file
    authserver_container = replace(authserver_container, can_connect=can_connect)
    state = State(containers=[authserver_container])

    # WHEN any event fires
    state_out = ctx.run(ctx.on.update_status(), state=state)

    # THEN the workload_version is unset
    assert not state_out.workload_version


def test_workload_version_set(ctx, authserver_container, version_file):
    # GIVEN a running auth container with a mounted version file
    authserver_container = replace(
        authserver_container,
        can_connect=True,
        mounts={"version-file": Mount(location="/VERSION", source=version_file)},
    )
    state = State(containers=[authserver_container])

    # WHEN any event fires
    state_out = ctx.run(ctx.on.update_status(), state=state)

    # THEN the workload_version is set
    assert state_out.workload_version
