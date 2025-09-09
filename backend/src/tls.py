#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from dataclasses import dataclass
from typing import Optional, Callable

from ops import Container

from charms.tls_certificates_interface.v4.tls_certificates import (
    ProviderCertificate,
    PrivateKey,
)

logger = logging.getLogger(__name__)


@dataclass
class TLSConfig:
    """TLS configuration received over the `tls-certificates` relation."""

    server_cert: str
    server_cert_path: str
    ca_cert: str
    ca_cert_path: str
    private_key: str
    private_key_path: str


class Tls:
    """Handle TLS certificates."""

    tls_cert_path = "/etc/tls/tls.crt"
    tls_key_path = "/etc/tls/tls.key"
    ca_cert_tls_path = "/etc/tls/ca.crt"

    def __init__(
        self,
        container: Container,
        tls_certs: Callable[
            [], tuple[Optional[ProviderCertificate], Optional[PrivateKey]]
        ],
    ):
        self._container = container
        self._certificates, self._private_key = tls_certs()

    def reconcile(self):
        if self._container.can_connect():
            self._reconcile_tls_config()

    def _reconcile_tls_config(self):
        if tls_config := self.tls_config:
            self._configure_tls(
                server_cert=tls_config.server_cert,
                ca_cert=tls_config.ca_cert,
                private_key=tls_config.private_key,
            )
            logger.info("Configured TLS for Litmus Backend.")
        else:
            self._delete_certificates()

    def _configure_tls(self, private_key: str, server_cert: str, ca_cert: str):
        """Save the certificates file to disk."""
        # Read the current content of the files (if they exist)
        current_server_cert = (
            self._container.pull(self.tls_cert_path).read()
            if self._container.exists(self.tls_cert_path)
            else ""
        )
        current_private_key = (
            self._container.pull(self.tls_key_path).read()
            if self._container.exists(self.tls_key_path)
            else ""
        )
        current_ca_cert = (
            self._container.pull(self.ca_cert_tls_path).read()
            if self._container.exists(self.ca_cert_tls_path)
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
        self._container.push(self.tls_key_path, private_key, make_dirs=True)
        self._container.push(self.tls_cert_path, server_cert, make_dirs=True)
        self._container.push(self.ca_cert_tls_path, ca_cert, make_dirs=True)
        logger.debug("TLS certificates pushed to the workload container.")

    def _delete_certificates(self) -> None:
        """Delete the certificate files from disk."""
        for path in (self.tls_cert_path, self.tls_key_path, self.ca_cert_tls_path):
            if self._container.exists(path):
                self._container.remove_path(path, recursive=True)
                logger.debug("TLS certificate removed: %s", path)

    @property
    def tls_config(self) -> Optional[TLSConfig]:
        """Returns the TLS configuration, including certificates and private key, if available; None otherwise."""
        if not (self._certificates and self._private_key):
            return None
        return TLSConfig(
            server_cert=self._certificates.certificate.raw,
            server_cert_path=self.tls_cert_path,
            ca_cert=self._certificates.ca.raw,
            ca_cert_path=self.ca_cert_tls_path,
            private_key=self._private_key.raw,
            private_key_path=self.tls_key_path,
        )
