# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import dataclasses
import pytest
from models import DatabaseConfig
from ops.testing import State


@pytest.mark.parametrize("leader", (False, True))
@pytest.mark.parametrize(
    "databag, expected",
    (
        ({}, None),
        (
            {"username": "admin", "password": "pass"},
            None,
        ),
        (
            {
                "username": "admin",
                "password": "pass",
                "uris": "uri.fqdn.1:port,uri.fqdn.2:port",
            },
            DatabaseConfig(
                username="admin",
                password="pass",
                uris="uri.fqdn.1:port,uri.fqdn.2:port",
            ),
        ),
    ),
)
def test_require_database(
    ctx, nginx_container, database_relation, databag, expected, leader
):
    # GIVEN a database integration with remote app data
    database_relation = dataclasses.replace(database_relation, remote_app_data=databag)

    # WHEN a relation_changed event fires
    with ctx(
        state=State(
            relations={database_relation}, containers={nginx_container}, leader=leader
        ),
        event=ctx.on.relation_changed(database_relation),
    ) as mgr:
        charm = mgr.charm
        # THEN the database_config is the same as expected
        assert charm.database_config == expected
