# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import json

import pytest
from ops import CharmBase
from ops.testing import Context, State
from scenario import Relation

from litmus_libs.interfaces.http_api import (
    LitmusAuthApiProvider,
    LitmusAuthApiRequirer,
    LitmusBackendApiProvider,
    LitmusBackendApiRequirer,
)


class HTTPAPICharm(CharmBase):
    META = {
        "name": "jonathan",
        "provides": {
            "send-auth-http": {"interface": "litmus_auth_http_api"},
            "send-backend-http": {"interface": "litmus_backend_http_api"},
        },
        "requires": {
            "receive-auth-http": {"interface": "litmus_auth_http_api"},
            "receive-backend-http": {"interface": "litmus_backend_http_api"},
        },
    }

    _IN = None
    _OUT = None, None

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.send_auth = LitmusAuthApiProvider(self.model.get_relation("send-auth-http"), self.app)
        self.receive_auth = LitmusAuthApiRequirer(
            self.model.get_relation("receive-auth-http"), self.app
        )
        self.send_backend = LitmusBackendApiProvider(
            self.model.get_relation("send-backend-http"), self.app
        )
        self.receive_backend = LitmusBackendApiRequirer(
            self.model.get_relation("receive-backend-http"), self.app
        )

        self._reconcile()

    def _reconcile(self):
        if self._IN:
            self.publish_endpoint(self._IN)

        HTTPAPICharm._OUT = self.receive_endpoints()

    def publish_endpoint(self, foo: str):
        self.send_auth.publish_endpoint(foo)
        self.send_backend.publish_endpoint(foo)
        self.receive_backend.publish_endpoint(foo)

    def receive_endpoints(self):
        return (
            self.receive_auth.auth_endpoint,
            self.receive_backend.backend_endpoint,
            self.send_backend.frontend_endpoint,
        )


@pytest.fixture(
    params=(
        "http://foo.com:2020/",
        "https://foo.com:2020/",
        "http://foo.com/",
    )
)
def endpoint(request):
    return request.param


def test_provider_publish_endpoint(endpoint):
    # GIVEN a charm that provides litmus_*_http_api
    ctx = Context(HTTPAPICharm, meta=HTTPAPICharm.META)

    # WHEN the charm publishes its endpoint
    HTTPAPICharm._IN = endpoint
    state_out = ctx.run(
        ctx.on.update_status(),
        state=State(
            relations={
                Relation("send-auth-http", id=1),
                Relation("send-backend-http", id=2),
                Relation("receive-backend-http", id=3),
            },
            leader=True,
        ),
    )

    # THEN the databags are populated as expected
    for rel_id in (1, 2):
        databag = state_out.get_relation(rel_id).local_app_data
        assert databag == {"version": json.dumps(0), "endpoint": json.dumps(endpoint)}


def test_requirer_receive_endpoint(endpoint):
    # GIVEN a charm that requires litmus_*_http_api
    ctx = Context(HTTPAPICharm, meta=HTTPAPICharm.META)

    databag = {"version": json.dumps(0), "endpoint": json.dumps(endpoint)}
    # WHEN the charm receives its endpoints
    ctx.run(
        ctx.on.update_status(),
        state=State(
            relations={
                Relation("receive-auth-http", id=1, remote_app_data=databag),
                Relation("receive-backend-http", id=2, remote_app_data=databag),
                Relation("send-backend-http", id=3, remote_app_data=databag),
            },
            leader=True,
        ),
    )

    # THEN the data is received as expected
    assert HTTPAPICharm._OUT == (endpoint, endpoint, endpoint)
