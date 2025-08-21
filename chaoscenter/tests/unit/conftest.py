# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

from ops.testing import Container, Context
import pytest
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
