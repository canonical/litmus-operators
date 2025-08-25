# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import dataclasses
import json

import pytest
from ops import CharmBase
from ops.testing import Context, Secret, State

from litmus_libs.interfaces import (
    AuthDataConfig,
    DexConfig,
    Endpoint,
    LitmusAuthDataProvider,
    LitmusAuthDataRequirer,
)

MOCK_SECRET_ID = "my_secret_id"


@pytest.mark.parametrize(
    "input, expected_secret_content",
    (
        (
            AuthDataConfig(
                grpc_server_host="host", grpc_server_port=80, dex_config=DexConfig(client_id="1")
            ),
            None,
        ),
        (
            AuthDataConfig(
                grpc_server_host="host",
                grpc_server_port=80,
                dex_config=DexConfig(
                    client_id="1", dex_oauth_client_secret="secret1", enabled=True
                ),
            ),
            {
                "dex-oauth-client-secret": "secret1",
            },
        ),
        (
            AuthDataConfig(
                grpc_server_host="host",
                grpc_server_port=80,
                dex_config=DexConfig(
                    client_id="1",
                    dex_oauth_client_secret="secret1",
                    oauth_jwt_secret="secret2",
                    enabled=True,
                ),
            ),
            {
                "dex-oauth-client-secret": "secret1",
                "oauth-jwt-secret": "secret2",
            },
        ),
    ),
)
def test_provider_publish_auth_data_secret(litmus_auth, input, expected_secret_content):
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
        # WHEN the charm publishes auth data
        provider = LitmusAuthDataProvider(
            charm.model.get_relation("litmus-auth"),
            charm.app,
            charm.model,
        )
        provider.publish_auth_data(input)

        # THEN the local app databag gets populated
        state_out = mgr.run()
        databag = state_out.get_relation(litmus_auth.id).local_app_data
        dex_config = json.loads(databag["dex_config"])

        # THEN dex config secret should be None if no secret content is expected
        if not expected_secret_content:
            assert dex_config["auth_secret_id"] is None
        else:
            # Otherwise, the dex config secret id must be set
            secret_id = dex_config["auth_secret_id"]
            assert secret_id
            # AND the secret's content must match the expected content
            secret = state_out.get_secret(id=secret_id)
            assert secret.tracked_content == expected_secret_content
            # AND the requirer should be granted access to the secret
            assert litmus_auth.id in secret.remote_grants.keys()


@pytest.mark.parametrize(
    "remote_databag, expected",
    (
        (
            {},
            None,
        ),
        (
            {"grpc_server_host": '"host"', "grpc_server_port": "80", "insecure": "false"},
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
        provider = LitmusAuthDataProvider(
            charm.model.get_relation("litmus-auth"),
            charm.app,
            charm.model,
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
        requirer = LitmusAuthDataRequirer(
            charm.model.get_relation("litmus-auth"),
            charm.app,
            charm.model,
        )
        # WHEN the requirer publishes its endpoint
        requirer.publish_endpoint(input)

        # THEN the local app databag is populated as expected
        state_out = mgr.run()
        databag = state_out.get_relation(litmus_auth.id).local_app_data
        assert databag == expected


@pytest.mark.parametrize(
    "remote_databag, secret_content, expected",
    (
        (
            {},
            None,
            None,
        ),
        (
            {
                "grpc_server_host": '"host"',
                "grpc_server_port": "80",
                "insecure": "false",
                "dex_config": "null",
            },
            None,
            AuthDataConfig(
                grpc_server_host="host", grpc_server_port=80, insecure=False, dex_config=None
            ),
        ),
        (
            {
                "grpc_server_host": '"host"',
                "grpc_server_port": "80",
                "insecure": "false",
                "dex_config": json.dumps(
                    {"client_id": "1", "auth_secret_id": MOCK_SECRET_ID, "enabled": True}
                ),
            },
            {"dex_oauth_client_secret": "secret1", "oauth_jwt_secret": "secret2"},
            AuthDataConfig(
                grpc_server_host="host",
                grpc_server_port=80,
                insecure=False,
                dex_config=DexConfig(
                    enabled=True,
                    client_id="1",
                    dex_oauth_client_secret="secret1",
                    oauth_jwt_secret="secret2",
                ),
            ),
        ),
    ),
)
def test_requirer_get_auth_data(litmus_auth, remote_databag, secret_content, expected):
    # GIVEN a charm that requires litmus-auth
    ctx = Context(
        CharmBase,
        meta={"name": "requirer", "requires": {"litmus-auth": {"interface": "litmus_auth"}}},
    )
    with ctx(
        # AND remote has published the auth data to the databag
        state=State(
            relations={dataclasses.replace(litmus_auth, remote_app_data=remote_databag)},
            leader=True,
            secrets={Secret(secret_content, id=MOCK_SECRET_ID)},
        ),
        event=ctx.on.update_status(),
    ) as mgr:
        charm = mgr.charm
        requirer = LitmusAuthDataRequirer(
            charm.model.get_relation("litmus-auth"),
            charm.app,
            charm.model,
        )
        # WHEN the requirer gets the published auth data
        auth_data = requirer.get_auth_data()
        # THEN the fetched data is the same as expected
        assert auth_data == expected
