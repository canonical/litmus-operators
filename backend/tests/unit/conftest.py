# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import json
from unittest.mock import patch
from ops.testing import Container, Context, Relation
import pytest
from charm import LitmusBackendCharm


@pytest.fixture
def backend_charm():
    with patch(
        "socket.getfqdn",
        return_value="app-0.app-headless.default.svc.cluster.local",
    ):
        yield LitmusBackendCharm


@pytest.fixture
def backend_container():
    return Container(
        "litmuschaos-server",
        can_connect=True,
    )


@pytest.fixture
def ctx(backend_charm):
    return Context(charm_type=backend_charm)


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
    }
