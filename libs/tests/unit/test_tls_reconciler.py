# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import Mock

from litmus_libs.tls_reconciler import TlsReconciler

SERVER_CERT_PATH = "/etc/tls/tls.crt"
PRIVATE_KEY_PATH = "/etc/tls/tls.key"
CA_CERT_PATH = "/usr/local/share/ca-certificates/ca.crt"


def test_reconcile_tls_config_not_called_if_cant_connect_to_workload_container(
    workload_container, tls_config
):
    tls = TlsReconciler(
        container=workload_container,
        tls_cert_path=SERVER_CERT_PATH,
        tls_key_path=PRIVATE_KEY_PATH,
        tls_ca_path=CA_CERT_PATH,
        tls_config_getter=lambda: tls_config,
    )
    tls._reconcile_tls_config = Mock()

    # GIVEN a workload container which can't be connected to
    workload_container.can_connect.return_value = False

    # WHEN tls.reconcile()
    tls.reconcile()

    # THEN _reconcile_tls_config() in not called
    tls._reconcile_tls_config.assert_not_called()


def test_certs_pushed_to_container_if_stored_certs_are_outdated(workload_container, tls_config):
    tls = TlsReconciler(
        container=workload_container,
        tls_cert_path=SERVER_CERT_PATH,
        tls_key_path=PRIVATE_KEY_PATH,
        tls_ca_path=CA_CERT_PATH,
        tls_config_getter=lambda: tls_config,
    )

    # GIVEN a workload container with outdated content
    workload_container.exists.side_effect = lambda path: True
    workload_container.pull.side_effect = lambda path: Mock(read=lambda: "outdated")

    # WHEN _configure_tls called with new TLS config
    tls._configure_tls(
        server_cert=tls_config.server_cert,
        private_key=tls_config.private_key,
        ca_cert=tls_config.ca_cert,
    )

    # THEN certs are updated in the workload container
    workload_container.push.assert_any_call(SERVER_CERT_PATH, "test_cert", make_dirs=True)
    workload_container.push.assert_any_call(PRIVATE_KEY_PATH, "test_key", make_dirs=True)
    workload_container.push.assert_any_call(CA_CERT_PATH, "test_ca", make_dirs=True)


def test_update_ca_certificates_is_run_after_certificates_are_pushed_to_workload_container(
    workload_container, tls_config
):
    tls = TlsReconciler(
        container=workload_container,
        tls_cert_path=SERVER_CERT_PATH,
        tls_key_path=PRIVATE_KEY_PATH,
        tls_ca_path=CA_CERT_PATH,
        tls_config_getter=lambda: tls_config,
    )

    # GIVEN a workload container with outdated content
    workload_container.exists.side_effect = lambda path: False

    # WHEN _configure_tls called with new TLS config
    tls._configure_tls(
        server_cert=tls_config.server_cert,
        private_key=tls_config.private_key,
        ca_cert=tls_config.ca_cert,
    )

    # THEN update-ca-certificates is run in the workload container
    workload_container.exec.assert_called_once_with(["update-ca-certificates", "--fresh"])


def test_certs_not_pushed_to_container_if_stored_certs_are_up_to_date(
    workload_container, tls_config
):
    tls = TlsReconciler(
        container=workload_container,
        tls_cert_path=SERVER_CERT_PATH,
        tls_key_path=PRIVATE_KEY_PATH,
        tls_ca_path=CA_CERT_PATH,
        tls_config_getter=lambda: tls_config,
    )

    # GIVEN a workload container with up-to-date content
    workload_container.exists.side_effect = lambda path: True
    workload_container.pull.side_effect = lambda path: Mock(
        read=lambda: {
            SERVER_CERT_PATH: "test_cert",
            PRIVATE_KEY_PATH: "test_key",
            CA_CERT_PATH: "test_ca",
        }[path]
    )

    # WHEN _configure_tls called with the same TLS config
    tls._configure_tls(
        server_cert=tls_config.server_cert,
        private_key=tls_config.private_key,
        ca_cert=tls_config.ca_cert,
    )

    # THEN certs are not updated in the workload container
    workload_container.push.assert_not_called()


def test_configure_tls_is_called_if_valid_tls_config_is_provider(workload_container, tls_config):
    # GIVEN valid TLS config
    tls = TlsReconciler(
        container=workload_container,
        tls_cert_path=SERVER_CERT_PATH,
        tls_key_path=PRIVATE_KEY_PATH,
        tls_ca_path=CA_CERT_PATH,
        tls_config_getter=lambda: tls_config,
    )
    tls._configure_tls = Mock()

    # WHEN _reconcile_tls_config is called
    tls._reconcile_tls_config()

    # THEN _configure_tls is called with provided TLS config
    tls._configure_tls.assert_called_once_with(
        server_cert=tls_config.server_cert,
        private_key=tls_config.private_key,
        ca_cert=tls_config.ca_cert,
    )


def test_delete_certificates_called_if_tls_config_is_none(workload_container):
    # GIVEN TLS config is None
    tls = TlsReconciler(
        container=workload_container,
        tls_cert_path=SERVER_CERT_PATH,
        tls_key_path=PRIVATE_KEY_PATH,
        tls_ca_path=CA_CERT_PATH,
        tls_config_getter=lambda: None,
    )
    tls._configure_tls = Mock()
    tls._delete_certificates = Mock()

    # WHEN _reconcile_tls_config is called
    tls._reconcile_tls_config()

    # THEN _delete_certificates is called to remove TLS config from the workload container
    tls._delete_certificates.assert_called_once()
