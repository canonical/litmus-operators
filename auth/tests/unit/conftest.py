# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
from contextlib import contextmanager
from unittest.mock import patch, Mock

import json
from ops.testing import Container, Context, Relation
import pytest
from charm import LitmusAuthCharm
from certificates_helpers import mock_cert_and_key


@pytest.fixture(scope="session")
def unit_fqdn():
    yield "app-0.app-headless.default.svc.cluster.local"


@pytest.fixture
def auth_charm(unit_fqdn):
    with patch(
        "socket.getfqdn",
        return_value=unit_fqdn,
    ):
        yield LitmusAuthCharm


@contextmanager
def patch_cert_and_key_ctx(tls: bool):
    tls_config = mock_cert_and_key() if tls else (None, None)
    with patch(
        "charms.tls_certificates_interface.v4.tls_certificates.TLSCertificatesRequiresV4.get_assigned_certificate",
        return_value=tls_config,
    ):
        yield tls_config


@pytest.fixture()
def patch_cert_and_key():
    with patch_cert_and_key_ctx(True) as tls_config:
        yield tls_config


@pytest.fixture(autouse=True)
def patch_container_exec():
    with patch(
        "ops.model.Container.exec",
        Mock(),
    ):
        yield


@pytest.fixture
def authserver_container():
    return Container(
        "auth",
        can_connect=True,
    )


@pytest.fixture
def ctx(auth_charm):
    yield Context(charm_type=auth_charm)


@pytest.fixture
def database_relation():
    return Relation("database")


@pytest.fixture
def auth_relation():
    return Relation("litmus-auth")


@pytest.fixture
def http_api_relation():
    return Relation("http-api")


@pytest.fixture
def tls_certificates_relation():
    return Relation("tls-certificates")


def db_remote_databag():
    return {
        "uris": "uris",
        "username": "username",
        "password": "password",
    }


def auth_remote_databag():
    return {
        "grpc_server_host": json.dumps("host"),
        "grpc_server_port": json.dumps(80),
        "version": json.dumps(0),
    }
