# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
from ops.testing import State


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


def test_pebble_ready_plan(
    ctx,
    nginx_container,
    nginx_prometheus_exporter_container,
    auth_http_api_relation,
    backend_http_api_relation,
):
    expected_plan = {
        "services": {
            "chaoscenter": {
                "override": "replace",
                "summary": "nginx",
                "command": "nginx -g 'daemon off;'",
                "startup": "enabled",
            },
        },
    }

    expected_nginx_prometheus_exporter_plan = {
        "services": {
            "nginx-prometheus-exporter": {
                "override": "replace",
                "summary": "nginx prometheus exporter",
                "command": "nginx-prometheus-exporter --no-nginx.ssl-verify --web.listen-address=:9113  --nginx.scrape-uri=http://127.0.0.1:8185/status",
                "startup": "enabled",
            }
        }
    }

    # GIVEN relations with auth and backend endpoints
    state = State(
        containers=[nginx_container, nginx_prometheus_exporter_container],
        relations=[auth_http_api_relation, backend_http_api_relation],
    )

    # WHEN a workload pebble ready event is fired
    state_out = ctx.run(ctx.on.pebble_ready(nginx_container), state=state)

    # THEN litmus auth server pebble plan is generated
    nginx_container_out = state_out.get_container(nginx_container.name)
    assert nginx_container_out.plan.to_dict() == expected_plan
    # AND the pebble service is running
    assert nginx_container_out.services.get("chaoscenter").is_running()
    # AND nginx prometheus exporter pebble plan is generated
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
