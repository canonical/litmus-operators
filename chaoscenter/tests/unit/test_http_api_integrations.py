from scenario import State


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
    # THEN chaoscenter charm publishes nothing
    assert not state_out.get_relation(backend_http_api_relation.id).local_app_data
    assert not state_out.get_relation(auth_http_api_relation.id).local_app_data
