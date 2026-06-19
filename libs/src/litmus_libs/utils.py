# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Collection of helper functions used across the litmus charms."""

import logging
import socket
from typing import Optional

from ops import Container

logger = logging.getLogger()


def get_app_hostname(app_name: str, model_name: str) -> str:
    """Return the FQDN of the k8s service associated with this application.

    This service load balances traffic across all application units.
    Falls back to this unit's DNS name if the hostname does not resolve to a Kubernetes-style fqdn.
    """
    hostname = socket.getfqdn()
    # hostname is expected to look like: 'app-0.app-headless.default.svc.cluster.local'
    hostname_parts = hostname.split(".")
    # 'svc' is always there in a K8s service fqdn
    # ref: https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/#services
    if "svc" not in hostname_parts:
        logger.debug(f"expected K8s-style fqdn, but got {hostname} instead")
        return hostname

    dns_name_parts = hostname_parts[hostname_parts.index("svc") :]
    dns_name = ".".join(dns_name_parts)  # 'svc.cluster.local'
    return f"{app_name}.{model_name}.{dns_name}"  # 'app.model.svc.cluster.local'


def get_litmus_version(container: Container) -> Optional[str]:
    """Get the running litmus version.

    Reads /VERSION if present; falls back to the version field in
    /.rock/metadata.yaml, which is always present in rock-based images.
    """
    if not container.can_connect():
        return None

    version_file_path = "/VERSION"
    if container.exists(version_file_path):
        return container.pull(version_file_path, encoding="utf-8").read().strip()

    rock_metadata_path = "/.rock/metadata.yaml"
    if container.exists(rock_metadata_path):
        content = container.pull(rock_metadata_path, encoding="utf-8").read()
        for line in content.splitlines():
            if line.startswith("version:"):
                return line.split(":", 1)[1].strip()

    logger.warning("Version not found at %s or %s", version_file_path, rock_metadata_path)
    return None
