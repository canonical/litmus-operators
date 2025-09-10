# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest
from ops.testing import Container, Relation
from litmus_libs.models import TLSConfig


@pytest.fixture(scope="function")
def litmus_auth():
    return Relation("litmus-auth")


@pytest.fixture
def workload_container():
    return Container(
        name="some-workload",
        can_connect=True,
    )


@pytest.fixture
def tls_config():
    return TLSConfig(
        server_cert = "some_cert",
        private_key = "some_key",
        ca_cert = "some_ca",
    )
