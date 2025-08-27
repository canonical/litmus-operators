# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
from unittest.mock import patch

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
    with patch("charm.get_app_hostname", new=lambda _, __: "foo.com"):
        yield Context(charm_type=backend_charm)


@pytest.fixture
def database_relation():
    return Relation("database")


@pytest.fixture
def http_api_relation():
    return Relation("http-api")
