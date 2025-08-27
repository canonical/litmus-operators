# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import dataclasses
import json

import pytest
from ops import CharmBase
from ops.testing import Context, State

from litmus_libs.interfaces.base import VersionMismatchError
from litmus_libs.interfaces.litmus_auth import (
    Endpoint,
    LitmusAuthProvider,
    LitmusAuthRequirer,
)


@pytest.mark.parametrize(
    "input, expected",
    (
        (
            Endpoint(
                grpc_server_host="host",
                grpc_server_port=80,
            ),
            {
                "grpc_server_host": json.dumps("host"),
                "grpc_server_port": json.dumps(80),
                "insecure": json.dumps(False),
                "version": json.dumps(0),
            },
        ),
        (
            Endpoint(
                grpc_server_host="host",
                grpc_server_port=80,
                insecure=True,
            ),
            {
                "grpc_server_host": json.dumps("host"),
                "grpc_server_port": json.dumps(80),
                "insecure": json.dumps(True),
                "version": json.dumps(0),
            },
        ),
    ),
)
def test_provider_publish_endpoint(litmus_auth, input, expected):
    # GIVEN a charm that provides litmus-auth
    ctx = Context(
        CharmBase,
        meta={"name": "provider", "provides": {"litmus-auth": {"interface": "litmus_auth"}}},
    )
    with ctx(
        state=State(
            relations={litmus_auth},
            leader=True,
        ),
        event=ctx.on.update_status(),
    ) as mgr:
        charm = mgr.charm
        # WHEN the charm publishes its endpoint
        provider = LitmusAuthProvider(
            charm.model.get_relation("litmus-auth"),
            charm.app,
        )
        provider.publish_endpoint(input)

        # THEN the local app databag gets populated with the expected content
        state_out = mgr.run()
        databag = state_out.get_relation(litmus_auth.id).local_app_data
        assert databag == expected


@pytest.mark.parametrize(
    "remote_databag, expected",
    (
        (
            {},
            None,
        ),
        (
            {
                "grpc_server_host": '"host"',
                "grpc_server_port": "80",
                "insecure": "false",
                "version": "0",
            },
            Endpoint(grpc_server_host="host", grpc_server_port=80, insecure=False),
        ),
    ),
)
def test_provider_get_backend_grpc_endpoint(litmus_auth, remote_databag, expected):
    # GIVEN a charm that provides litmus-auth
    ctx = Context(
        CharmBase,
        meta={"name": "provider", "provides": {"litmus-auth": {"interface": "litmus_auth"}}},
    )
    with ctx(
        # AND remote has published its endpoint to the databag
        state=State(
            relations={dataclasses.replace(litmus_auth, remote_app_data=remote_databag)},
            leader=True,
        ),
        event=ctx.on.update_status(),
    ) as mgr:
        charm = mgr.charm
        provider = LitmusAuthProvider(
            charm.model.get_relation("litmus-auth"),
            charm.app,
        )
        assert provider.get_backend_grpc_endpoint() == expected


@pytest.mark.parametrize(
    "input, expected",
    (
        (
            Endpoint(grpc_server_host="host", grpc_server_port=80, insecure=False),
            {
                "grpc_server_host": '"host"',
                "grpc_server_port": "80",
                "insecure": "false",
                "version": "0",
            },
        ),
    ),
)
def test_requirer_publish_endpoint(litmus_auth, input, expected):
    # GIVEN a charm that requires litmus-auth
    ctx = Context(
        CharmBase,
        meta={"name": "requirer", "requires": {"litmus-auth": {"interface": "litmus_auth"}}},
    )
    with ctx(
        state=State(
            relations={litmus_auth},
            leader=True,
        ),
        event=ctx.on.update_status(),
    ) as mgr:
        charm = mgr.charm
        requirer = LitmusAuthRequirer(
            charm.model.get_relation("litmus-auth"),
            charm.app,
        )
        # WHEN the requirer publishes its endpoint
        requirer.publish_endpoint(input)

        # THEN the local app databag is populated as expected
        state_out = mgr.run()
        databag = state_out.get_relation(litmus_auth.id).local_app_data
        assert databag == expected


@pytest.mark.parametrize(
    "remote_databag, expected",
    (
        (
            {},
            None,
        ),
        (
            {
                "grpc_server_host": '"host"',
                "grpc_server_port": "80",
                "insecure": "false",
                "version": "0",
            },
            Endpoint(
                grpc_server_host="host",
                grpc_server_port=80,
                insecure=False,
            ),
        ),
        (
            {
                "grpc_server_host": '"host"',
                "grpc_server_port": "80",
                "insecure": "true",
                "version": "0",
            },
            Endpoint(
                grpc_server_host="host",
                grpc_server_port=80,
                insecure=True,
            ),
        ),
    ),
)
def test_requirer_get_auth_grpc_endpoint(litmus_auth, remote_databag, expected):
    # GIVEN a charm that requires litmus-auth
    ctx = Context(
        CharmBase,
        meta={"name": "requirer", "requires": {"litmus-auth": {"interface": "litmus_auth"}}},
    )
    with ctx(
        # AND remote has published its endpoint to the databag
        state=State(
            relations={dataclasses.replace(litmus_auth, remote_app_data=remote_databag)},
            leader=True,
        ),
        event=ctx.on.update_status(),
    ) as mgr:
        charm = mgr.charm
        requirer = LitmusAuthRequirer(
            charm.model.get_relation("litmus-auth"),
            charm.app,
        )
        # WHEN the requirer gets the published endpoint
        endpoint = requirer.get_auth_grpc_endpoint()
        # THEN the fetched data is the same as expected
        assert endpoint == expected


def test_fail_version_mismatch(litmus_auth):
    # GIVEN a charm that provides litmus-auth
    ctx = Context(
        CharmBase,
        meta={"name": "provider", "provides": {"litmus-auth": {"interface": "litmus_auth"}}},
    )

    # WHEN the charm receives its endpoints
    with ctx(
        ctx.on.update_status(),
        state=State(
            relations={
                dataclasses.replace(
                    litmus_auth,
                    remote_app_data={
                        "version": json.dumps(42),
                        "foo": '"bar"',
                    },
                )
            },
            leader=True,
        ),
    ) as mgr:
        charm = mgr.charm
        provider = LitmusAuthProvider(
            charm.model.get_relation("litmus-auth"),
            charm.app,
        )
        # THEN the charm raises an exception if it receives a version the lib doesn't support
        with pytest.raises(VersionMismatchError):
            assert provider.get_backend_grpc_endpoint()
