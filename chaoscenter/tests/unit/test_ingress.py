from scenario import State

import ops


def test_ingressed_url_present_in_status(
    ctx,
    nginx_container,
    nginx_prometheus_exporter_container,
    auth_http_api_relation,
    backend_http_api_relation,
    ingress_relation,
    user_secret,
    user_secrets_config,
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
            containers={nginx_container, nginx_prometheus_exporter_container},
            config=user_secrets_config,
            secrets=[user_secret],
        ),
    )

    # THEN juju status reports an ingressed url
    assert state_out.unit_status == ops.ActiveStatus("Ready at http://1.2.3.4:8185.")


def test_ingressed_https_url_present_in_status(
    ctx,
    nginx_container,
    nginx_prometheus_exporter_container,
    auth_http_api_relation,
    backend_http_api_relation,
    ingress_over_https_relation,
    tls_certificates_relation,
    patch_cert_and_key,
    patch_write_to_ca_path,
    user_secret,
    user_secrets_config,
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
                ingress_over_https_relation,
                tls_certificates_relation,
            },
            containers={nginx_container, nginx_prometheus_exporter_container},
            config=user_secrets_config,
            secrets=[user_secret],
        ),
    )

    # THEN juju status reports an ingressed url
    assert state_out.unit_status == ops.ActiveStatus("Ready at https://1.2.3.4:8185.")
