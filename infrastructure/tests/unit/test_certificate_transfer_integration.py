import json
from unittest.mock import patch
from ops.testing import Relation, State


@patch("subprocess.run")
def test_ca_certs_write_on_disk(mock_run, ctx, mock_cert_path):
    # GIVEN a a charm integrated over receive-ca-certs relation
    # AND remote sends some certs
    certs_rel = Relation(
        endpoint="receive-ca-certs",
        remote_app_data={"certificates": json.dumps(["cert1", "cert2"])},
    )
    state = State(relations={certs_rel})

    # WHEN any event is fired
    with patch("charm.TRUSTED_CA_CERT_PATH", mock_cert_path):
        ctx.run(ctx.on.update_status(), state)

    # THEN verify that the certs have been written to disk
    assert mock_cert_path.read_text() == "cert1\ncert2"
    # AND update-ca-certificates command has been called
    mock_run.assert_called_once_with(["update-ca-certificates", "--fresh"])


def test_ca_certs_removed_when_relation_empty(ctx, mock_cert_path):
    # GIVEN the CA cert file already exists on disk
    mock_cert_path.parent.mkdir(parents=True, exist_ok=True)
    mock_cert_path.write_text("old-cert")

    # AND a relation exists but provides no certificates
    certs_rel = Relation(
        endpoint="receive-ca-certs",
        remote_app_data={"certificates": json.dumps([])},
    )
    state = State(relations={certs_rel})

    # WHEN any event is fired
    with patch("charm.TRUSTED_CA_CERT_PATH", mock_cert_path):
        ctx.run(ctx.on.update_status(), state)

    # THEN the certificate file is removed from the disk
    assert not mock_cert_path.exists()


@patch("subprocess.run")
def test_ca_certs_idempotency(mock_run, ctx, mock_cert_path):
    # GIVEN the cert file already exists on disk with specific content
    mock_cert_path.parent.mkdir(parents=True, exist_ok=True)
    mock_cert_path.write_text("cert1\ncert2")

    # AND the remote sends the EXACT same certs
    certs_rel = Relation(
        endpoint="receive-ca-certs",
        remote_app_data={"certificates": json.dumps(["cert1", "cert2"])},
    )
    state = State(relations={certs_rel})

    # WHEN any event is fired
    with patch("charm.TRUSTED_CA_CERT_PATH", mock_cert_path):
        ctx.run(ctx.on.update_status(), state)

    # THEN verify that the file content remains unchanged
    assert mock_cert_path.read_text() == "cert1\ncert2"

    # AND verify that update-ca-certificates was NOT called
    mock_run.assert_not_called()
