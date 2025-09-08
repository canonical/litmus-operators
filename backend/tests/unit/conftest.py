# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
from unittest.mock import patch

import json
from ops.testing import Container, Context, Relation
import pytest
from charm import LitmusBackendCharm
from certificates_helpers import example_cert_and_key


@pytest.fixture
def backend_charm():
    with patch(
        "socket.getfqdn",
        return_value="app-0.app-headless.default.svc.cluster.local",
    ):
        yield LitmusBackendCharm


@pytest.fixture()
def get_assigned_certs():
    provider_certificate, private_key = example_cert_and_key()
    with patch(
        "charms.tls_certificates_interface.v4.tls_certificates.TLSCertificatesRequiresV4.get_assigned_certificate",
        return_value=(provider_certificate, private_key),
    ) as get_cert:
        yield get_cert


@pytest.fixture
def backend_container():
    return Container(
        "backend",
        can_connect=True,
    )


@pytest.fixture
def ctx(backend_charm):
    yield Context(charm_type=backend_charm)


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
        "version": json.dumps(0),
        "grpc_server_host": json.dumps("host"),
        "grpc_server_port": json.dumps(80),
    }


def http_api_remote_databag():
    return {
        "version": json.dumps(0),
        "endpoint": json.dumps("http://foo.com:8080"),
    }
