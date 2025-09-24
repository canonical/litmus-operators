# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import io

import pytest

from litmus_libs.utils import get_litmus_version


class MockContainer:
    """A lightweight mock of `ops.Container` used for testing."""

    def __init__(self, can_connect=True, file_exists=True, file_content="fake_version"):
        self._can_connect = can_connect
        self._file_exists = file_exists
        self._file_content = file_content

    def can_connect(self):
        return self._can_connect

    def exists(self, _):
        return self._file_exists

    def pull(self, _, encoding=None):
        return io.StringIO(self._file_content)


@pytest.mark.parametrize("can_connect", (False, True))
def test_litmus_version_empty(can_connect):
    # GIVEN a container with no mounted version file
    test_container = MockContainer(can_connect=can_connect, file_exists=False)

    # WHEN get_litmus_version is called with that container
    version = get_litmus_version(container=test_container)

    # THEN we get an empty version string
    assert not version


def test_litmus_version_not_empty():
    # GIVEN a running test container with a mounted version file
    test_container = MockContainer(can_connect=True, file_exists=True)

    # WHEN get_litmus_version is called with that container
    version = get_litmus_version(container=test_container)

    # THEN we get a non empty version string
    assert version
