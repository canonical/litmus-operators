# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import dataclasses
import pytest
import json

from ops import BlockedStatus, ActiveStatus

from conftest import patch_cert_and_key_ctx
from litmus_libs.interfaces.litmus_auth import Endpoint
from ops.testing import State, Model, CharmEvents


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
                "version": json.dumps(0),
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
def test_publish_endpoint_without_tls(
    ctx, auth_relation, backend_container, leader, expected
):
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
                "grpc_server_port": json.dumps(8001),
                "insecure": json.dumps(False),
                "version": json.dumps(0),
            },
        ),
    ),
)
def test_publish_endpoint_with_tls(
    ctx,
    auth_relation,
    tls_certificates_relation,
    patch_cert_and_key,
    backend_container,
    leader,
    expected,
):
    # GIVEN an auth integration
    auth_relation = dataclasses.replace(auth_relation)
    tls_certificates_relation = dataclasses.replace(tls_certificates_relation)

    # WHEN a relation_changed event fires
    state_out = ctx.run(
        state=State(
            relations={auth_relation, tls_certificates_relation},
            containers={backend_container},
            leader=leader,
            model=Model(name="test"),
        ),
        event=ctx.on.relation_changed(auth_relation),
    )

    # THEN the leader unit will publish it's grpc server endpoint
    relation_out = state_out.get_relation(auth_relation.id)
    assert relation_out.local_app_data == expected


@pytest.mark.parametrize("leader", (False, True))
@pytest.mark.parametrize("backend_tls", (False, True))
@pytest.mark.parametrize("local_tls", (False, True))
@pytest.mark.parametrize(
    "event",
    (
        CharmEvents.upgrade_charm(),
        CharmEvents.install(),
        CharmEvents.update_status(),
        CharmEvents.install(),
    ),
)
def test_tls_consistency(
    ctx,
    auth_relation,
    event,
    authserver_container,
    leader,
    backend_tls,
    local_tls,
    database_relation,
    tls_certificates_relation,
):
    # GIVEN a litmus-auth integration with remote app data (secure or not)
    auth_relation = dataclasses.replace(
        auth_relation,
        remote_app_data={
            "grpc_server_host": json.dumps("host"),
            "grpc_server_port": json.dumps(80),
            "version": json.dumps(0),
            "insecure": json.dumps(not backend_tls),
        },
    )
    database_relation = dataclasses.replace(
        database_relation,
        remote_app_data={
            "username": "admin",
            "password": "pass",
            "uris": "uri.fqdn.1:port,uri.fqdn.2:port",
        },
    )

    # WHEN any event fires
    with patch_cert_and_key_ctx(local_tls):
        state_out = ctx.run(
            state=State(
                relations={
                    auth_relation,
                    database_relation,
                    *((tls_certificates_relation,) if local_tls else ()),
                },
                containers={authserver_container},
                leader=leader,
            ),
            event=event,
        )

    # THEN only in the inconsistent scenario we set blocked
    expect_inconsistent = backend_tls and not local_tls
    if expect_inconsistent:
        assert isinstance(state_out.unit_status, BlockedStatus)
    else:
        assert isinstance(state_out.unit_status, ActiveStatus)
