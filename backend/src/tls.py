#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from dataclasses import dataclass
from typing import Optional, List

from charms.tls_certificates_interface.v4.tls_certificates import (
    TLSCertificatesRequiresV4,
    CertificateRequestAttributes,
)
from ops import Container, Relation

logger = logging.getLogger(__name__)


@dataclass
class TLSConfig:
    """TLS configuration received by the coordinator over the `certificates` relation.

    This is an internal object that we use as facade so that the individual Coordinator charms don't have to know the API of the charm libs that implements the relation interface.
    """

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
        tls_certificates: TLSCertificatesRequiresV4,
        certificate_request_attributes: CertificateRequestAttributes,
        tls_certificates_relation: Optional[List[Relation]],
    ):
        self._container = container
        self._tls_certificates = tls_certificates
        self._certificate_request_attributes = certificate_request_attributes
        self._tls_certificates_relation = tls_certificates_relation

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
        if not self._tls_certificates_relation:
            return None
        certificates, key = self._tls_certificates.get_assigned_certificate(
            certificate_request=self._certificate_request_attributes
        )
        if not (key and certificates):
            return None
        return TLSConfig(
            server_cert=certificates.certificate.raw,
            server_cert_path=self.tls_cert_path,
            ca_cert=certificates.ca.raw,
            ca_cert_path=self.ca_cert_tls_path,
            private_key=key.raw,
            private_key_path=self.tls_key_path,
        )
