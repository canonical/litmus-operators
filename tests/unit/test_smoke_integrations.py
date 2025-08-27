import pytest
from ops.testing import Context
from scenario import State, Relation

from auth.src.charm import LitmusAuthCharm
from backend.src.charm import LitmusBackendCharm
from chaoscenter.src.charm import LitmusChaoscenterCharm
from litmus_libs.interfaces.http_api import AuthApiProviderAppDatabagModelV0, BackendApiProviderAppDatabagModelV0


@pytest.fixture
def auth_ctx():
    return Context(LitmusAuthCharm)


@pytest.fixture
def backend_ctx():
    return Context(LitmusBackendCharm)


def test_auth_endpoints(auth_ctx):
    # GIVEN an http api relation
    http_api_relation = Relation("http-api")
    # WHEN the charm receives any event
    state_out = auth_ctx.run(
        auth_ctx.on.update_status(),
        state=State(leader=True, relations={http_api_relation}),
    )
    # THEN auth publishes its endpoint data
    assert AuthApiProviderAppDatabagModelV0.model_validate(state_out.get_relation(http_api_relation.id).local_app_data)


