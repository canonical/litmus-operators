# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

from ops.testing import Container, Context, Relation
import pytest
from charm import LitmusBackendCharm


@pytest.fixture
def backend_charm():
    yield LitmusBackendCharm


@pytest.fixture
def backend_container():
    return Container(
        "litmuschaos-server",
        can_connect=True,
    )


@pytest.fixture
def ctx(backend_charm):
    return Context(charm_type=backend_charm)


@pytest.fixture
def database_relation():
    return Relation("database")
