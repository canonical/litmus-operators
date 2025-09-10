#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Shared module for handling TLS configuration in Charmed Litmus."""

import logging
from typing import Callable, Optional

from ops import Container

from litmus_libs.models import TLSConfig

logger = logging.getLogger(__name__)


class Tls:
    """Handle TLS certificates."""

    def __init__(
        self,
        container: Container,
        tls_cert_path: str,
        tls_key_path: str,
        tls_ca_path: str,
        tls_config_getter: Callable[[], Optional[TLSConfig]],
    ):
        self._container = container
        self._tls_cert_path = tls_cert_path
        self._tls_key_path = tls_key_path
        self._tls_ca_path = tls_ca_path
        self._tls_config_getter = tls_config_getter

    def reconcile(self):
        """If the workload container can be connected to, configure TLS."""
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
        # Read the current content of the files (if they exist)
        current_server_cert = (
            self._container.pull(self._tls_cert_path).read()
            if self._container.exists(self._tls_cert_path)
            else ""
        )
        current_private_key = (
            self._container.pull(self._tls_key_path).read()
            if self._container.exists(self._tls_key_path)
            else ""
        )
        current_ca_cert = (
            self._container.pull(self._tls_ca_path).read()
            if self._container.exists(self._tls_ca_path)
            else ""
        )

        if (
            current_server_cert == server_cert
            and current_private_key == private_key
            and current_ca_cert == ca_cert
        ):
            # No update needed
            logger.debug("TLS certificates up to date. Skipping update.")
            return
        self._container.push(self._tls_cert_path, server_cert, make_dirs=True)
        self._container.push(self._tls_key_path, private_key, make_dirs=True)
        self._container.push(self._tls_ca_path, ca_cert, make_dirs=True)
        logger.debug("TLS certificates pushed to the workload container.")

    def _delete_certificates(self) -> None:
        """Delete the certificate files from disk."""
        for path in (self._tls_cert_path, self._tls_key_path, self._tls_ca_path):
            if self._container.exists(path):
                self._container.remove_path(path, recursive=True)
                logger.debug("TLS certificate removed: %s", path)
