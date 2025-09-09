# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
from unittest.mock import patch

import json
from ops.testing import Container, Context, Relation
import pytest
from charm import LitmusAuthCharm
from certificates_helpers import mock_cert_and_key


@pytest.fixture
def auth_charm():
    with patch(
        "socket.getfqdn",
        return_value="app-0.app-headless.default.svc.cluster.local",
    ):
        yield LitmusAuthCharm


@pytest.fixture
def cert_and_key():
    return mock_cert_and_key()


@pytest.fixture()
def patch_cert_and_key(cert_and_key):
    with patch(
        "charms.tls_certificates_interface.v4.tls_certificates.TLSCertificatesRequiresV4.get_assigned_certificate",
        return_value=cert_and_key,
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
