# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import sys
from pathlib import Path

import pytest
from ops import CharmBase
from ops.testing import Context, State
from scenario import Relation

# we cannot import self_monitoring without pretending we're running this from a charm's POV,
# because the module attempts to import charm libraries.
# Hopefully some day we can treat charmlibs like regular python deps...
sys.path.append(
    str((Path(__file__).parent.parent.parent.parent / "chaoscenter" / "lib").absolute())
)

from litmus_libs.interfaces.self_monitoring import SelfMonitoring


class MyCharm(CharmBase):
    META = {
        "name": "echo",
        "requires": {
            "charm-tracing": {"interface": "tracing"},
            "workload-tracing": {"interface": "tracing"},
            "logging": {"interface": "loki_push_api"},
            "tls-certificates": {"interface": "tls_certificates"},
        },
        "provides": {
            "prometheus-scrape": {"interface": "prometheus_scrape"},
            "grafana-dashboard": {"interface": "grafana_dashboard"},
        },
    }

    BAD_META_1 = {
        "name": "gecko",
        "requires": {"logging": {"interface": "loki_push_api"}},
    }

    BAD_META_2 = {
        "name": "gecko",
        "requires": {"logging": {"interface": "something-weird"}},
    }

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._self_monitoring = SelfMonitoring(
            self,
            workload_tracing_protocols=["otlp_grpc", "zipkin"],
            prometheus_scrape_jobs=[{"foo": ["bar:baz"]}],
        )


def test_init_fails_if_meta_missing_relations():
    with pytest.raises(Exception):
        ctx = Context(MyCharm, meta=MyCharm.BAD_META_1)
        ctx.run(ctx.on.update_status(), State())


def test_init_fails_if_meta_bad_interfaces():
    with pytest.raises(Exception):
        ctx = Context(MyCharm, meta=MyCharm.BAD_META_2)
        ctx.run(ctx.on.update_status(), State())


@pytest.fixture
def ctx():
    return Context(MyCharm, meta=MyCharm.META)


def test_tracing_integration(ctx):
    # GIVEN a tracing relation
    tracing_relation = Relation("workload-tracing")
    state = State(leader=True, relations=[tracing_relation])
    # WHEN we receive any event
    state_out = ctx.run(ctx.on.update_status(), state)
    # THEN we have published our requested endpoints
    assert "receivers" in state_out.get_relation(tracing_relation.id).local_app_data

    # GIVEN a tracing relation with remote data
    tracing_relation = Relation(
        "workload-tracing",
        remote_app_data={
            "receivers": '[{{"protocol": {{"name": "otlp_grpc", "type": "grpc"}}, "url": "hostname:4317"}}, '
            '{{"protocol": {{"name": "otlp_http", "type": "http"}}, "url": "http://hostname:4318"}}, '
            '{{"protocol": {{"name": "zipkin", "type": "http"}}, "url": "http://hostname:9411" }}]',
        },
    )
    state = State(leader=True, relations=[tracing_relation])
    # WHEN we receive any event
    with ctx(ctx.on.update_status(), state) as mgr:
        charm: MyCharm = mgr.charm
        # THEN the charm can access the endpoints
        assert charm._self_monitoring.get_workload_tracing_endpoints("otlp_grpc")


def test_prometheus_scrape_integration(ctx):
    # GIVEN a tracing relation
    prom_scrape_relation = Relation("prometheus-scrape")
    state = State(leader=True, relations=[prom_scrape_relation])
    # WHEN we receive any event
    state_out = ctx.run(ctx.on.update_status(), state)
    # THEN we have published our requested endpoints
    assert "alert_rules" in state_out.get_relation(prom_scrape_relation.id).local_app_data
