# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

from ops.testing import Context
import pytest
from charm import LitmusInfrastructureCharm


@pytest.fixture(scope="session")
def unit_fqdn():
    yield "app-0.app-headless.default.svc.cluster.local"


@pytest.fixture
def infra_charm():
    yield LitmusInfrastructureCharm


@pytest.fixture
def ctx(infra_charm):
    yield Context(charm_type=infra_charm)
