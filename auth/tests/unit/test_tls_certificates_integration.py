# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import os
import tempfile
from pathlib import Path

from ops.testing import Mount, State


def test_tls_certs_saved_to_the_disk_when_available_in_tls_certificates_relation_databag(
    ctx, authserver_container, tls_certificates_relation, patch_cert_and_key
):
    # GIVEN a running container with a tls-certificates relation
    state = State(
        containers=[authserver_container], relations=[tls_certificates_relation]
    )

    # WHEN a relation changed event is fired
    state_out = ctx.run(ctx.on.relation_changed(tls_certificates_relation), state=state)

    # THEN TLS certs are stored in the workload container
    authserver_container_out = state_out.get_container(authserver_container.name)

    assert os.path.exists(
        f"{authserver_container_out.get_filesystem(ctx)}/etc/tls/tls.crt"
    )
    assert os.path.exists(
        f"{authserver_container_out.get_filesystem(ctx)}/etc/tls/tls.key"
    )
    assert os.path.exists(
        f"{authserver_container_out.get_filesystem(ctx)}/usr/local/share/ca-certificates/ca.crt"
    )


def test_tls_certs_removed_from_disk_when_tls_certificates_relation_is_broken(
    ctx, authserver_container, tls_certificates_relation
):
    with tempfile.TemporaryDirectory() as tempdir:
        certs_mount = Mount(
            location="/etc",
            source=Path(tempdir) / "etc",
        )
        usr_mount = Mount(
            location="/usr",
            source=Path(tempdir) / "usr",
        )
        authserver_container.mounts["certs"] = certs_mount
        authserver_container.mounts["usr"] = usr_mount

        # GIVEN a running container with a tls-certificates relation and TLS certs stored on the disk
        state = State(
            containers=[authserver_container], relations=[tls_certificates_relation]
        )
        os.makedirs(f"{tempdir}/etc/tls", exist_ok=True)
        os.makedirs(f"{tempdir}/usr/local/share/ca-certificates", exist_ok=True)

        with open(f"{tempdir}/etc/tls/tls.crt", "w") as f:
            f.write("certificate")
        with open(f"{tempdir}/etc/tls/tls.key", "w") as f:
            f.write("private key")
        with open(f"{tempdir}/usr/local/share/ca-certificates/ca.crt", "w+") as f:
            f.write("ca cert")

        # WHEN a relation broken event is fired
        ctx.run(ctx.on.relation_broken(tls_certificates_relation), state=state)

        # THEN TLS certs are removed from the workload container
        assert not os.path.exists(f"{tempdir}/tls.crt")
        assert not os.path.exists(f"{tempdir}/tls.key")
        assert not os.path.exists(f"{tempdir}/usr/local/share/ca-certificates/ca.crt")


def test_tls_certs_not_updated_if_stored_certs_match_these_from_the_relation_databag(
    ctx,
    authserver_container,
    tls_certificates_relation,
    cert_and_key,
    patch_cert_and_key,
):
    with tempfile.TemporaryDirectory() as tempdir:
        certs_mount = Mount(
            location="/etc",
            source=Path(tempdir) / "etc",
        )
        usr_mount = Mount(
            location="/usr",
            source=Path(tempdir) / "usr",
        )
        certs, key = cert_and_key
        authserver_container.mounts["certs"] = certs_mount
        authserver_container.mounts["usr"] = usr_mount

        # GIVEN a running container with a tls-certificates relation and up-to-date TLS certs stored on the disk
        state = State(
            containers=[authserver_container], relations=[tls_certificates_relation]
        )
        os.makedirs(f"{tempdir}/etc/tls", exist_ok=True)
        os.makedirs(f"{tempdir}/usr/local/share/ca-certificates", exist_ok=True)

        with open(f"{tempdir}/etc/tls/tls.crt", "w") as f:
            f.write(str(certs.certificate))
        with open(f"{tempdir}/etc/tls/tls.key", "w") as f:
            f.write(str(key))
        with open(f"{tempdir}/usr/local/share/ca-certificates/ca.crt", "w+") as f:
            f.write(str(certs.ca))
        cert_modification_time = os.stat(f"{tempdir}/etc/tls/tls.crt").st_mtime
        key_modification_time = os.stat(f"{tempdir}/etc/tls/tls.key").st_mtime
        ca_modification_time = os.stat(
            f"{tempdir}/usr/local/share/ca-certificates/ca.crt"
        ).st_mtime

        # WHEN a relation changed event is fired
        ctx.run(ctx.on.relation_changed(tls_certificates_relation), state=state)

        # THEN TLS certs stored in the workload container aren't changed
        assert os.stat(f"{tempdir}/etc/tls/tls.crt").st_mtime == cert_modification_time
        assert os.stat(f"{tempdir}/etc/tls/tls.key").st_mtime == key_modification_time
        assert (
            os.stat(f"{tempdir}/usr/local/share/ca-certificates/ca.crt").st_mtime
            == ca_modification_time
        )


def test_tls_certs_updated_if_stored_certs_dont_match_these_from_the_relation_databag(
    ctx,
    authserver_container,
    tls_certificates_relation,
    cert_and_key,
    patch_cert_and_key,
):
    with tempfile.TemporaryDirectory() as tempdir:
        certs_mount = Mount(
            location="/etc",
            source=Path(tempdir) / "etc",
        )
        usr_mount = Mount(
            location="/usr",
            source=Path(tempdir) / "usr",
        )
        certs, key = cert_and_key
        authserver_container.mounts["certs"] = certs_mount
        authserver_container.mounts["usr"] = usr_mount

        # GIVEN a running container with a tls-certificates relation and outdated TLS certs stored on the disk
        state = State(
            containers=[authserver_container], relations=[tls_certificates_relation]
        )
        os.makedirs(f"{tempdir}/etc/tls", exist_ok=True)
        os.makedirs(f"{tempdir}/usr/local/share/ca-certificates", exist_ok=True)

        with open(f"{tempdir}/etc/tls/tls.crt", "w") as f:
            f.write("certificate")
        with open(f"{tempdir}/etc/tls/tls.key", "w") as f:
            f.write("private key")
        with open(f"{tempdir}/usr/local/share/ca-certificates/ca.crt", "w+") as f:
            f.write("ca cert")

        # WHEN a relation changed event is fired
        ctx.run(ctx.on.relation_changed(tls_certificates_relation), state=state)

        # THEN TLS certs stored in the workload container are updated
        with open(f"{tempdir}/etc/tls/tls.crt", "r") as f:
            assert f.read() == str(certs.certificate)
        with open(f"{tempdir}/etc/tls/tls.key", "r") as f:
            assert f.read() == str(key)
        with open(f"{tempdir}/usr/local/share/ca-certificates/ca.crt", "r") as f:
            assert f.read() == str(certs.ca)
