# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
from unittest.mock import Mock

import pytest
from ops.testing import Relation

from litmus_libs.models import TLSConfigData


@pytest.fixture(scope="function")
def litmus_auth():
    return Relation("litmus-auth")


@pytest.fixture
def workload_container():
    return Mock()


@pytest.fixture
def tls_paths():
    return {
        "server_cert_path": "/etc/tls/tls.crt",
        "private_key_path": "/etc/tls/tls.key",
        "ca_cert_path": "/usr/local/share/ca-certificates/ca.crt",
    }


@pytest.fixture
def tls_config():
    return TLSConfigData(
        server_cert="test_cert",
        private_key="test_key",
        ca_cert="test_ca",
    )
