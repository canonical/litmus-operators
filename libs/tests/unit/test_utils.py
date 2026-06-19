# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import io

import pytest

from litmus_libs.utils import get_litmus_version


class MockContainer:
    """A lightweight mock of `ops.Container` used for testing."""

    def __init__(self, can_connect=True, files: dict | None = None):
        self._can_connect = can_connect
        self._files: dict[str, str] = files or {}

    def can_connect(self):
        return self._can_connect

    def exists(self, path):
        return path in self._files

    def pull(self, path, encoding=None):
        return io.StringIO(self._files[path])


@pytest.mark.parametrize("can_connect", (False, True))
def test_litmus_version_empty_no_files(can_connect):
    # GIVEN a container with neither /VERSION nor /.rock/metadata.yaml
    test_container = MockContainer(can_connect=can_connect, files={})

    # WHEN get_litmus_version is called
    version = get_litmus_version(container=test_container)

    # THEN we get no version
    assert not version


def test_litmus_version_from_version_file():
    # GIVEN a container with a /VERSION file
    test_container = MockContainer(files={"/VERSION": "3.26.0\n"})

    # WHEN get_litmus_version is called
    version = get_litmus_version(container=test_container)

    # THEN we get the version from /VERSION (stripped)
    assert version == "3.26.0"


def test_litmus_version_from_rock_metadata_fallback():
    # GIVEN a container without /VERSION but with /.rock/metadata.yaml
    rock_metadata = "name: litmuschaos-server\nversion: 3.29.0\nsummary: foo\n"
    test_container = MockContainer(files={"/.rock/metadata.yaml": rock_metadata})

    # WHEN get_litmus_version is called
    version = get_litmus_version(container=test_container)

    # THEN we get the version from the rock metadata
    assert version == "3.29.0"


def test_litmus_version_prefers_version_file_over_rock_metadata():
    # GIVEN a container with both /VERSION and /.rock/metadata.yaml
    rock_metadata = "name: litmuschaos-server\nversion: 3.29.0\n"
    test_container = MockContainer(
        files={"/VERSION": "3.26.0", "/.rock/metadata.yaml": rock_metadata}
    )

    # WHEN get_litmus_version is called
    version = get_litmus_version(container=test_container)

    # THEN /VERSION takes precedence
    assert version == "3.26.0"


def test_litmus_version_not_empty():
    # GIVEN a running container with a mounted version file
    test_container = MockContainer(files={"/VERSION": "fake_version"})

    # WHEN get_litmus_version is called
    version = get_litmus_version(container=test_container)

    # THEN we get a non-empty version string
    assert version
