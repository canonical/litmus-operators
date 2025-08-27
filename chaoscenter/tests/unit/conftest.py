# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

from ops.testing import Container, Context
import pytest
from scenario import Relation

from charm import LitmusChaoscenterCharm


@pytest.fixture
def chaoscenter_charm():
    yield LitmusChaoscenterCharm


@pytest.fixture
def nginx_container():
    return Container(
        "nginx",
        can_connect=True,
    )


@pytest.fixture
def ctx(chaoscenter_charm):
    return Context(charm_type=chaoscenter_charm)


@pytest.fixture
def auth_http_api_relation():
    return Relation("auth-http-api")


@pytest.fixture
def backend_http_api_relation():
    return Relation("backend-http-api")
