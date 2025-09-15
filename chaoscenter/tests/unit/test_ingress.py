from scenario import State

import ops


def test_ingressed_url_present_in_status(
    ctx,
    nginx_container,
    auth_http_api_relation,
    backend_http_api_relation,
    ingress_relation,
):
    # GIVEN http api relations with auth and backend and ingress
    # WHEN any event happens
    state_out = ctx.run(
        ctx.on.update_status(),
        state=State(
            leader=True,
            relations={
                auth_http_api_relation,
                backend_http_api_relation,
                ingress_relation,
            },
            containers={nginx_container},
        ),
    )

    # THEN juju status reports an ingressed url
    assert state_out.unit_status == ops.ActiveStatus("Ready at http://1.2.3.4:8185.")
