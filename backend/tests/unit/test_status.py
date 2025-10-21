# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import dataclasses
import pytest
import ops
from ops.testing import State, CharmEvents, Relation, CheckInfo
from conftest import db_remote_databag, auth_remote_databag, http_api_remote_databag
from ops.pebble import Layer, CheckStatus


@pytest.mark.parametrize("leader", (False, True))
@pytest.mark.parametrize(
    "event",
    (
        CharmEvents.upgrade_charm(),
        CharmEvents.install(),
        CharmEvents.update_status(),
        CharmEvents.install(),
    ),
)
@pytest.mark.parametrize(
    "relations",
    (
        {},
        {Relation("database")},
        {Relation("litmus-auth")},
    ),
)
def test_missing_relations_blocked_status(
    ctx, relations, event, backend_container, leader
):
    # GIVEN a running container
    # AND the relations provided by input (if any)
    # WHEN we receive any event
    state_out = ctx.run(
        event, State(containers={backend_container}, leader=leader, relations=relations)
    )
    # THEN the unit sets blocked
    assert isinstance(state_out.unit_status, ops.BlockedStatus)


@pytest.mark.parametrize(
    "event",
    (
        CharmEvents.upgrade_charm(),
        CharmEvents.install(),
        CharmEvents.update_status(),
        CharmEvents.install(),
    ),
)
@pytest.mark.parametrize(
    "data_missing_from",
    ("database", "litmus-auth", "http-api"),
)
def test_waiting_status(ctx, data_missing_from, event, backend_container):
    # GIVEN a running container
    # AND remote hasn't sent any data yet for any one relation
    required_relations = {
        "database": Relation("database", remote_app_data=db_remote_databag()),
        "litmus-auth": Relation("litmus-auth", remote_app_data=auth_remote_databag()),
        "http-api": Relation("http-api", remote_app_data=http_api_remote_databag()),
    }

    relation_missing_remote_data = dataclasses.replace(
        required_relations.pop(data_missing_from), remote_app_data={}
    )
    # WHEN we receive any event
    state_out = ctx.run(
        event,
        State(
            containers={backend_container},
            relations={relation_missing_remote_data, *required_relations.values()},
        ),
    )
    # THEN the unit sets waiting
    assert isinstance(state_out.unit_status, ops.WaitingStatus)


@pytest.mark.parametrize(
    "event",
    (
        CharmEvents.upgrade_charm(),
        CharmEvents.install(),
        CharmEvents.update_status(),
        CharmEvents.install(),
    ),
)
def test_active_status(
    ctx, database_relation, auth_relation, http_api_relation, backend_container, event
):
    # GIVEN a running container
    # AND a database and a litmus-auth relation
    # AND remotes have sent their data
    database_relation = dataclasses.replace(
        database_relation, remote_app_data=db_remote_databag()
    )
    auth_relation = dataclasses.replace(
        auth_relation, remote_app_data=auth_remote_databag()
    )
    http_api_relation = dataclasses.replace(
        http_api_relation, remote_app_data=http_api_remote_databag()
    )
    # WHEN we receive any event
    state_out = ctx.run(
        event,
        State(
            containers={backend_container},
            relations={database_relation, auth_relation, http_api_relation},
        ),
    )
    # THEN the unit sets active
    assert isinstance(state_out.unit_status, ops.ActiveStatus)


@pytest.mark.parametrize(
    "event",
    (
        CharmEvents.upgrade_charm(),
        CharmEvents.install(),
        CharmEvents.update_status(),
        CharmEvents.install(),
    ),
)
def test_pebble_check_failing_blocked_status(
    ctx,
    database_relation,
    auth_relation,
    backend_container,
    event,
):
    # GIVEN a database and a litmus-auth relation
    # AND an backend container with failing pebble checks
    backend_container = dataclasses.replace(
        backend_container,
        layers={
            "backend": Layer(
                {
                    "services": {"backend": {}},
                    "checks": {
                        "backend-up": {
                            "threshold": 3,
                            "startup": "enabled",
                            "level": None,
                        }
                    },
                }
            )
        },
        check_infos={CheckInfo("backend-up", status=CheckStatus.DOWN, level=None)},
    )
    state = State(
        containers=[backend_container],
        relations=[database_relation, auth_relation],
    )

    # WHEN any event fires
    state_out = ctx.run(event, state=state)

    # THEN the unit sets blocked
    assert isinstance(state_out.unit_status, ops.BlockedStatus)
