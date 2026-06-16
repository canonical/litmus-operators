import pytest
import json
from unittest.mock import patch
from ops.testing import State, Relation


@pytest.mark.parametrize("tls", [True, False])
@patch("ops_tracing.set_destination")
def test_charm_tracing(mock_set_destination, ctx, mock_cert_path, tls):
    # GIVEN a charm with tracing relation
    # AND a remote endpoint that may or may not use TLS
    protocol = "https" if tls else "http"
    endpoint = f"{protocol}://tempo:4318"

    tracing_rel = Relation(
        endpoint="charm-tracing",
        remote_app_data={
            "receivers": f'[{{"protocol": {{"name": "otlp_http", "type": "http"}}, "url": "{endpoint}"}}]',
        },
    )
    relations = {tracing_rel}

    # AND IF tls is True, we add the CA certificate relation
    if tls:
        certs_rel = Relation(
            endpoint="receive-ca-certs",
            remote_app_data={"certificates": json.dumps(["my-ca-cert"])},
        )
        relations.add(certs_rel)

    state = State(relations=relations)

    # WHEN any event is fired
    with patch("charm.TRUSTED_CA_CERT_PATH", mock_cert_path):
        ctx.run(ctx.on.update_status(), state)

    # THEN verify that tracing is configured with the correct URL
    # AND the CA is provided ONLY when tls was True
    mock_set_destination.assert_called_once_with(
        url=f"{endpoint}/v1/traces", ca="my-ca-cert" if tls else None
    )
