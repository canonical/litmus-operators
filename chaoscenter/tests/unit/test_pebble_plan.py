# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
from unittest.mock import PropertyMock, patch

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
    # GIVEN relations with auth and backend endpoints
    state = State(
        containers=[nginx_container, nginx_prometheus_exporter_container],
        relations=[auth_http_api_relation, backend_http_api_relation],
    )

    with patch_cert_and_key_ctx(tls):
        # WHEN a workload pebble ready event is fired
        state_out = ctx.run(ctx.on.pebble_ready(nginx_container), state=state)

    nginx_container_out = state_out.get_container(nginx_container.name)
    nginx_container_plan = nginx_container_out.plan
    # THEN litmus chaoscenter server pebble plan is generated with the correct command
    assert (
        nginx_container_plan.services["chaoscenter"].command == "nginx -g 'daemon off;'"
    )
    # AND the correct on-check-failure
    assert nginx_container_plan.services["chaoscenter"].on_check_failure == {
        "chaoscenter-up": "restart"
    }

    # AND the plan has the correct pebble checks
    assert nginx_container_plan.checks["chaoscenter-up"].http == {
        "url": f"http{'s' if tls else ''}://{unit_fqdn}:8185/health"
    }
    # AND the pebble service is running
    assert nginx_container_out.services.get("chaoscenter").is_running()

    # AND the charm status is active
    assert state_out.unit_status.name == "active"


@pytest.mark.parametrize(
    "tls",
    (
        False,
        True,
    ),
)
def test_nginx_exporter_pebble_ready_plan(
    ctx,
    nginx_container,
    nginx_prometheus_exporter_container,
    auth_http_api_relation,
    backend_http_api_relation,
    tls,
):
    expected_cmd_args = {
        "nginx-prometheus-exporter",
        "--web.listen-address=:9113",
        f"--nginx.scrape-uri=http{'s' if tls else ''}://127.0.0.1:{'443' if tls else '8185'}/status",
        "--no-nginx.ssl-verify",
        "--web.config.file=/etc/exporter/web-config.yaml",
    }

    # GIVEN relations with auth and backend endpoints
    state = State(
        containers=[nginx_container, nginx_prometheus_exporter_container],
        relations=[auth_http_api_relation, backend_http_api_relation],
    )

    with patch(
        "coordinated_workers.nginx.NginxPrometheusExporter.are_certificates_on_disk",
        new_callable=PropertyMock(return_value=tls),
    ):
        # WHEN a workload pebble ready event is fired
        state_out = ctx.run(
            ctx.on.pebble_ready(nginx_prometheus_exporter_container), state=state
        )

    # THEN nginx prometheus exporter pebble plan is generated
    nginx_prometheus_exporter_container_out = state_out.get_container(
        nginx_prometheus_exporter_container.name
    )
    generated_plan = nginx_prometheus_exporter_container_out.plan.to_dict()
    assert (
        set(generated_plan["services"]["nginx-prometheus-exporter"]["command"].split())
        == expected_cmd_args
    ), f"Generated plan: {generated_plan}"

    # AND the prometheus-exporter pebble service is running
    assert nginx_prometheus_exporter_container_out.services.get(
        "nginx-prometheus-exporter"
    ).is_running()

    # AND the charm status is active
    assert state_out.unit_status.name == "active"
