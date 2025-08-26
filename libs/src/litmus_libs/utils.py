# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Collection of helper functions used across the litmus charms."""

import logging
import socket

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
