# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import pytest
from ops import CharmBase
from ops.testing import Context, State
from scenario import Relation

from litmus_libs.interfaces.self_monitoring import SelfMonitoring


class MyCharm(CharmBase):
    META = {
        "name": "echo",
        "requires": {
            "ch-tracing": {"interface": "tracing"},
            "logging": {"interface": "loki_push_api"},
            "cert-transfer": {"interface": "certificate_transfer"},
        },
    }

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._self_monitoring = SelfMonitoring(
            self,
            endpoint_overrides={
                "charm-tracing": "ch-tracing",  # non-default!
            },
        )


@pytest.mark.parametrize(
    "bad_meta",
    (
        {
            "name": "gecko",
            # missing required charm-tracing
            "requires": {"logging": {"interface": "loki_push_api"}},
        },
        {
            "name": "gecko",
            # logging has bad interface name
            "requires": {
                "logging": {"interface": "something-weird"},
                "charm-tracing": {"interface": "tracing"},
            },
        },
    ),
)
def test_init_fails_if_bad_meta(bad_meta):
    with pytest.raises(Exception):
        ctx = Context(MyCharm, meta=bad_meta)
        ctx.run(ctx.on.update_status(), State())


@pytest.fixture
def ctx():
    return Context(MyCharm, meta=MyCharm.META)


def test_tracing_integration(ctx):
    # GIVEN a tracing relation
    tracing_relation = Relation("ch-tracing")
    state = State(leader=True, relations=[tracing_relation])
    # WHEN we receive any event
    state_out = ctx.run(ctx.on.update_status(), state)
    # THEN we have published our requested endpoints
    assert "receivers" in state_out.get_relation(tracing_relation.id).local_app_data

    # GIVEN a tracing relation with remote data
    tracing_relation = Relation(
        "ch-tracing",
        remote_app_data={
            "receivers": '[{{"protocol": {{"name": "otlp_grpc", "type": "grpc"}}, "url": "hostname:4317"}}, '
            '{{"protocol": {{"name": "otlp_http", "type": "http"}}, "url": "http://hostname:4318"}}, '
            '{{"protocol": {{"name": "zipkin", "type": "http"}}, "url": "http://hostname:9411" }}]',
        },
    )
    state = State(leader=True, relations=[tracing_relation])
    # WHEN we receive any event, the charm doesn't error out
    ctx.run(ctx.on.update_status(), state)


def test_logging_integration(ctx):
    # GIVEN a logging relation with remote data
    logging_relation = Relation(
        "logging",
        remote_app_data={},
    )
    state = State(leader=True, relations=[logging_relation])
    # WHEN we receive any event
    state_out = ctx.run(ctx.on.update_status(), state)

    # THEN all sidecars get injected with a log-forwarding layer
    for container_out in state_out.containers:
        assert container_out.plan.services["log-forwarding"]
