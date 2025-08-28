import json

from scenario import State

from litmus_libs.interfaces.http_api import BackendApiRequirerAppDatabagModelV0


def test_chaoscenter_endpoints(
    ctx, nginx_container, auth_http_api_relation, backend_http_api_relation
):
    # GIVEN http api relations with auth and backend
    # WHEN the charm receives any event
    state_out = ctx.run(
        ctx.on.update_status(),
        state=State(
            leader=True,
            relations={auth_http_api_relation, backend_http_api_relation},
            containers={nginx_container},
        ),
    )

    # THEN chaoscenter publishes its endpoint data
    def _dejsonify(d: dict):
        return {k: json.loads(v) for k, v in d.items()}

    assert BackendApiRequirerAppDatabagModelV0.model_validate(
        _dejsonify(state_out.get_relation(backend_http_api_relation.id).local_app_data)
    )

    # THEN chaoscenter charm publishes nothing over auth-http-api
    assert not state_out.get_relation(auth_http_api_relation.id).local_app_data
