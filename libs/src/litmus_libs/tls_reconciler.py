#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Shared module for handling TLS configuration in Charmed Litmus."""

import logging
from typing import Callable, Optional

from ops import Container

from litmus_libs.models import TLSConfigData

logger = logging.getLogger(__name__)


class TlsReconciler:
    """Synchronize the tls configuration data received over an integration, with a container's filesystem."""

    def __init__(
        self,
        container: Container,
        tls_cert_path: str,
        tls_key_path: str,
        tls_ca_path: str,
        tls_config_getter: Callable[[], Optional[TLSConfigData]],
    ):
        self._container = container
        self._tls_cert_path = tls_cert_path
        self._tls_key_path = tls_key_path
        self._tls_ca_path = tls_ca_path
        self._tls_config_getter = tls_config_getter

    def reconcile(self):
        """If the workload container can be connected to, synchronize the TLS configuration."""
        if self._container.can_connect():
            self._reconcile_tls_config()

    def _reconcile_tls_config(self):
        if tls_config := self._tls_config_getter():
            self._configure_tls(
                server_cert=tls_config.server_cert,
                private_key=tls_config.private_key,
                ca_cert=tls_config.ca_cert,
            )
        else:
            self._delete_certificates()

    def _configure_tls(self, server_cert: str, private_key: str, ca_cert: str):
        """Save the certificates file to disk."""
        for contents, filepath in (
            (server_cert, self._tls_cert_path),
            (ca_cert, self._tls_ca_path),
            (private_key, self._tls_key_path),
        ):
            current_contents = (
                self._container.pull(filepath).read() if self._container.exists(filepath) else ""
            )

            if current_contents == contents:
                # No update needed
                logger.debug("%s unchanged; skipping update.", filepath)
                continue

            # TODO: For charm tracing TLS certs need to be pushed to charm container as well. Charm tracing implementation requires https://github.com/canonical/litmus-operators/pull/40
            self._container.push(filepath, contents, make_dirs=True)
        logger.debug("TLS certificates pushed to the workload container.")

        self._container.exec(["update-ca-certificates", "--fresh"]).wait()
        logger.debug("CA certificates updated successfully.")

    def _delete_certificates(self) -> None:
        """Delete the certificate files from disk."""
        for path in (self._tls_cert_path, self._tls_key_path, self._tls_ca_path):
            if self._container.exists(path):
                self._container.remove_path(path, recursive=True)
                logger.debug("TLS certificate removed: %s", path)
