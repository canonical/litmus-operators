# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

from ops.testing import Container, Context, Relation
import pytest
from charm import LitmusAuthCharm


@pytest.fixture
def auth_charm():
    yield LitmusAuthCharm


@pytest.fixture
def authserver_container():
    return Container(
        "authserver",
        can_connect=True,
    )


@pytest.fixture
def ctx(auth_charm):
    return Context(charm_type=auth_charm)


@pytest.fixture
def database_relation():
    return Relation("database")
