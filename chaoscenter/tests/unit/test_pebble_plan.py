# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
from ops.testing import State
import pytest
from conftest import patch_cert_and_key_ctx


def test_pebble_empty_plan(ctx, nginx_container, nginx_prometheus_exporter_container):
    expected_plan = {}

    # GIVEN no relations
    state = State(
        containers=[nginx_container, nginx_prometheus_exporter_container], relations=[]
    )

    # WHEN a workload pebble ready event is fired
    state_out = ctx.run(ctx.on.pebble_ready(nginx_container), state=state)

    # THEN no pebble plan is generated
    nginx_container_out = state_out.get_container(nginx_container.name)
    assert nginx_container_out.plan.to_dict() == expected_plan
    # AND the pebble service is NOT present
    assert not nginx_container_out.services.get("chaoscenter")

    # AND the charm status is waiting
    assert state_out.unit_status.name == "blocked"


@pytest.mark.parametrize("tls", (False, True))
def test_nginx_pebble_ready_plan(
    ctx,
    nginx_container,
    nginx_prometheus_exporter_container,
    auth_http_api_relation,
    backend_http_api_relation,
    unit_fqdn,
    patch_write_to_ca_path,
    tls,
):
    expected_plan = {
        "services": {
            "chaoscenter": {
                "override": "replace",
                "summary": "nginx",
                "command": "nginx -g 'daemon off;'",
                "startup": "enabled",
                "on-check-failure": {
                    "chaoscenter": "restart",
                },
            },
        },
        "checks": {
            "chaoscenter": {
                "override": "replace",
                "startup": "enabled",
                "threshold": 3,
                "http": {"url": f"http{'s' if tls else ''}://{unit_fqdn}:8185/health"},
            }
        },
    }

    # GIVEN relations with auth and backend endpoints
    state = State(
        containers=[nginx_container, nginx_prometheus_exporter_container],
        relations=[auth_http_api_relation, backend_http_api_relation],
    )

    with patch_cert_and_key_ctx(tls):
        # WHEN a workload pebble ready event is fired
        state_out = ctx.run(ctx.on.pebble_ready(nginx_container), state=state)

    # THEN litmus chaoscenter server pebble plan is generated
    nginx_container_out = state_out.get_container(nginx_container.name)
    assert nginx_container_out.plan.to_dict() == expected_plan
    # AND the pebble service is running
    assert nginx_container_out.services.get("chaoscenter").is_running()

    # AND the charm status is active
    assert state_out.unit_status.name == "active"


@pytest.mark.parametrize(
    "tls",
    (
        False,
        pytest.param(
            True,
            marks=pytest.mark.skip(
                reason="TODO: https://github.com/canonical/cos-coordinated-workers/issues/71"
            ),
        ),
    ),
)
def test_nginx_exporter_pebble_ready_plan(
    ctx,
    nginx_container,
    nginx_prometheus_exporter_container,
    auth_http_api_relation,
    backend_http_api_relation,
    patch_write_to_ca_path,
    tls,
):
    expected_nginx_prometheus_exporter_plan = {
        "services": {
            "nginx-prometheus-exporter": {
                "override": "replace",
                "summary": "nginx prometheus exporter",
                "command": f"nginx-prometheus-exporter --no-nginx.ssl-verify --web.listen-address=:9113  --nginx.scrape-uri=http{'s' if tls else ''}://127.0.0.1:8185/status",
                "startup": "enabled",
            }
        }
    }

    # GIVEN relations with auth and backend endpoints
    state = State(
        containers=[nginx_container, nginx_prometheus_exporter_container],
        relations=[auth_http_api_relation, backend_http_api_relation],
    )

    with patch_cert_and_key_ctx(tls):
        # WHEN a workload pebble ready event is fired
        state_out = ctx.run(ctx.on.pebble_ready(nginx_container), state=state)

    # THEN nginx prometheus exporter pebble plan is generated
    nginx_prometheus_exporter_container_out = state_out.get_container(
        nginx_prometheus_exporter_container.name
    )
    assert (
        nginx_prometheus_exporter_container_out.plan.to_dict()
        == expected_nginx_prometheus_exporter_plan
    )
    # AND the prometheus-exporter pebble service is running
    assert nginx_prometheus_exporter_container_out.services.get(
        "nginx-prometheus-exporter"
    ).is_running()

    # AND the charm status is active
    assert state_out.unit_status.name == "active"
