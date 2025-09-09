#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import socket
from dataclasses import dataclass
from typing import Optional

from charms.tls_certificates_interface.v4.tls_certificates import (
    CertificateRequestAttributes,
    TLSCertificatesRequiresV4,
)
from ops import CharmBase, Container

logger = logging.getLogger(__name__)


@dataclass
class TLSConfig:
    """TLS configuration received by the coordinator over the `certificates` relation.

    This is an internal object that we use as facade so that the individual Coordinator charms don't have to know the API of the charm libs that implements the relation interface.
    """

    server_cert: str
    ca_cert: str
    private_key: str


class Tls:
    """Handle TLS certificates."""

    tls_cert_path = "/etc/tls/tls.crt"
    tls_key_path = "/etc/tls/tls.key"
    ca_cert_tls_path = "/etc/tls/ca.crt"

    def __init__(
        self,
        charm: CharmBase,
        relation_name: str,
        container: Container,
    ):
        self._charm = charm
        self._relation_name = relation_name
        self._container = container
        self._certificates = TLSCertificatesRequiresV4(
            charm=charm,
            relationship_name=relation_name,
            certificate_requests=[self._certificate_request_attributes],
        )

    def reconcile(self):
        self._certificates.sync()
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
        if not self._charm.model.relations.get(self._relation_name):
            return None
        certificates, key = self._certificates.get_assigned_certificate(
            certificate_request=self._certificate_request_attributes
        )
        if not (key and certificates):
            return None
        return TLSConfig(certificates.certificate.raw, certificates.ca.raw, key.raw)

    @property
    def _certificate_request_attributes(self) -> CertificateRequestAttributes:
        return CertificateRequestAttributes(
            common_name=self._charm.app.name,
            sans_dns=frozenset(socket.getfqdn()),
        )
