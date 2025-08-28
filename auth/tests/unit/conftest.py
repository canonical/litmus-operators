# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
from unittest.mock import patch

import json
from ops.testing import Container, Context, Relation
import pytest
from charm import LitmusAuthCharm


@pytest.fixture
def auth_charm():
    with patch(
        "socket.getfqdn",
        return_value="app-0.app-headless.default.svc.cluster.local",
    ):
        yield LitmusAuthCharm


@pytest.fixture
def authserver_container():
    return Container(
        "authserver",
        can_connect=True,
    )


@pytest.fixture
def ctx(auth_charm):
    with patch("charm.get_app_hostname", new=lambda _, __: "foo.com"):
        yield Context(charm_type=auth_charm)


@pytest.fixture
def database_relation():
    return Relation("database")


@pytest.fixture
def auth_relation():
    return Relation("litmus-auth")


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


@pytest.fixture
def http_api_relation():
    return Relation("http-api")
