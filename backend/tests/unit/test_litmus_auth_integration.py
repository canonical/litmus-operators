# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import dataclasses
import pytest
import json
from litmus_libs.interfaces import Endpoint
from ops.testing import State, Model


@pytest.mark.parametrize("leader", (False, True))
@pytest.mark.parametrize(
    "databag, expected",
    (
        ({}, None),
        (
            {"grpc_server_host": json.dumps("host")},
            None,
        ),
        (
            {
                "grpc_server_host": json.dumps("host"),
                "grpc_server_port": json.dumps(80),
                "insecure": json.dumps(True),
            },
            Endpoint(
                grpc_server_host="host",
                grpc_server_port=80,
                insecure=True,
            ),
        ),
    ),
)
def test_get_auth_grpc_endpoint(
    ctx, auth_relation, backend_container, databag, expected, leader
):
    # GIVEN an auth integration with remote app data
    auth_relation = dataclasses.replace(auth_relation, remote_app_data=databag)

    # WHEN a relation_changed event fires
    with ctx(
        state=State(
            relations={auth_relation}, containers={backend_container}, leader=leader
        ),
        event=ctx.on.relation_changed(auth_relation),
    ) as mgr:
        charm = mgr.charm
        # THEN the auth_grpc_endpoint is the same as expected
        assert charm.auth_grpc_endpoint == expected


@pytest.mark.parametrize(
    "leader, expected",
    (
        (False, {}),
        (
            True,
            {
                "grpc_server_host": json.dumps(
                    "litmus-backend-k8s.test.svc.cluster.local"
                ),
                "grpc_server_port": json.dumps(8000),
                "insecure": json.dumps(True),
                "version": json.dumps(0),
            },
        ),
    ),
)
def test_publish_endpoint(ctx, auth_relation, backend_container, leader, expected):
    # GIVEN an auth integration
    auth_relation = dataclasses.replace(auth_relation)

    # WHEN a relation_changed event fires
    state_out = ctx.run(
        state=State(
            relations={auth_relation},
            containers={backend_container},
            leader=leader,
            model=Model(name="test"),
        ),
        event=ctx.on.relation_changed(auth_relation),
    )

    # THEN the leader unit will publish it's grpc server endpoint
    relation_out = state_out.get_relation(auth_relation.id)
    assert relation_out.local_app_data == expected
