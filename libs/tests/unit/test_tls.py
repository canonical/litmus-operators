# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import tempfile

from ops.testing import Mount


def test_tls_certs_saved_to_the_disk_when_available_in_tls_certificates_relation_databag(
    ctx, workload_container, tls_config
):
    with tempfile.TemporaryDirectory() as tempdir:
        certs_mount = Mount(
            location="/etc/tls",
            source=tempdir,
        )