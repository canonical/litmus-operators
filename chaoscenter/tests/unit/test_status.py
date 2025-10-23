# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import json

import ops
from ops.testing import State, CheckInfo, CharmEvents
from dataclasses import replace
from ops.pebble import Layer
from ops.pebble import CheckStatus
import pytest
from ops.testing import Relation, Context

from charm import LitmusChaoscenterCharm


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
    nginx_container,
    nginx_prometheus_exporter_container,
    auth_http_api_relation,
    backend_http_api_relation,
    event,
):
    # GIVEN relations with auth and backend endpoints
    # AND a chaoscenter container with failing pebble checks
    nginx_container = replace(
        nginx_container,
        layers={
            "chaoscenter": Layer(
                {
                    "services": {"chaoscenter": {}},
                    "checks": {
                        "chaoscenter-up": {
                            "threshold": 3,
                            "startup": "enabled",
                            "level": None,
                        }
                    },
                }
            )
        },
        check_infos={CheckInfo("chaoscenter-up", status=CheckStatus.DOWN, level=None)},
    )
    state = State(
        containers=[nginx_container, nginx_prometheus_exporter_container],
        relations=[auth_http_api_relation, backend_http_api_relation],
    )

    # WHEN any event fires
    state_out = ctx.run(event, state=state)

    # THEN the unit sets blocked
    assert isinstance(state_out.unit_status, ops.BlockedStatus)


@pytest.fixture
def auth_https_api_relation():
    return Relation(
        "auth-http-api",
        remote_app_data={
            "version": json.dumps(0),
            "endpoint": json.dumps("https://foo.bar:3000"),
        },
    )


@pytest.fixture
def backend_https_api_relation():
    return Relation(
        "backend-http-api",
        remote_app_data={
            "version": json.dumps(0),
            "endpoint": json.dumps("https://foo.bar:8080"),
        },
    )


@pytest.mark.parametrize(
    "event",
    (
        CharmEvents.upgrade_charm(),
        CharmEvents.install(),
        CharmEvents.update_status(),
        CharmEvents.install(),
    ),
)
def test_tls_inconsistent_blocked_status(
    ctx: Context[LitmusChaoscenterCharm],
    nginx_container,
    nginx_prometheus_exporter_container,
    auth_https_api_relation,
    backend_https_api_relation,
    event,
):
    # GIVEN relations with auth and backend HTTPS endpoints
    state = State(
        containers=[nginx_container, nginx_prometheus_exporter_container],
        relations=[auth_https_api_relation, backend_https_api_relation],
    )

    # WHEN any event fires
    with ctx(event, state=state) as mgr:
        charm = mgr.charm
        assert not charm._tls_config
        assert charm._is_missing_tls_certificate
        state_out = mgr.run()

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
def test_tls_waiting_status(
    ctx: Context[LitmusChaoscenterCharm],
    nginx_container,
    nginx_prometheus_exporter_container,
    auth_https_api_relation,
    backend_https_api_relation,
    tls_certificates_relation,
    event,
):
    # GIVEN relations with auth and backend HTTPS endpoints, and a tls certificate relation but no certs yet
    state = State(
        containers=[nginx_container, nginx_prometheus_exporter_container],
        relations=[
            auth_https_api_relation,
            backend_https_api_relation,
            tls_certificates_relation,
        ],
    )

    # WHEN any event fires
    with ctx(event, state=state) as mgr:
        charm = mgr.charm
        assert not charm._tls_config
        assert charm._is_missing_tls_certificate
        state_out = mgr.run()

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
def test_tls_active_status(
    ctx: Context[LitmusChaoscenterCharm],
    nginx_container,
    nginx_prometheus_exporter_container,
    auth_https_api_relation,
    backend_https_api_relation,
    tls_certificates_relation,
    patch_cert_and_key,
    patch_write_to_ca_path,
    event,
):
    # GIVEN relations with auth and backend HTTPS endpoints, and a well-configured tls certificate relation (see patches)
    state = State(
        containers=[nginx_container, nginx_prometheus_exporter_container],
        relations=[
            auth_https_api_relation,
            backend_https_api_relation,
            tls_certificates_relation,
        ],
    )

    # WHEN any event fires
    with ctx(event, state=state) as mgr:
        charm = mgr.charm
        assert charm._tls_config
        assert not charm._is_missing_tls_certificate
        state_out = mgr.run()

    # THEN the unit sets active
    assert isinstance(state_out.unit_status, ops.ActiveStatus)
