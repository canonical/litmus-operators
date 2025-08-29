import json

from scenario import State
from litmus_libs.interfaces.http_api import BackendApiProviderAppDatabagModelV0


def test_backend_endpoints(
    ctx, backend_container, database_relation, http_api_relation
):
    # GIVEN an http api relation
    # WHEN the charm receives any event
    state_out = ctx.run(
        ctx.on.update_status(),
        state=State(
            leader=True,
            relations={http_api_relation, database_relation},
            containers={backend_container},
        ),
    )

    # THEN backend publishes its endpoint data
    def _dejsonify(d: dict):
        return {k: json.loads(v) for k, v in d.items()}

    assert BackendApiProviderAppDatabagModelV0.model_validate(
        _dejsonify(state_out.get_relation(http_api_relation.id).local_app_data)
    )
