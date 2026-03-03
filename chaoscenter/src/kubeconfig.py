#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper for generating content of the KUBECONFIG file."""

import logging
import yaml
from pathlib import Path

from lightkube import KubeConfig
from lightkube.core.exceptions import ConfigError


logger = logging.getLogger(__name__)


KUBECONFIG_API_VERSION = "v1"
KUBECONFIG_KIND = "Config"
KUBECONFIG_PATH = Path("/.kube/config")


class KubeconfigError(Exception):
    """Exception raised when Kubeconfig can't be generated."""

    def __init__(self, msg: str):
        self.msg = msg


def generate_kubeconfig() -> str:
    try:
        config = KubeConfig.from_service_account()
    except ConfigError as e:
        raise KubeconfigError("Unable to get Kubernetes config from SA.") from e

    if not config.current_context:
        raise KubeconfigError("Unable to get current Kubernetes context.")

    kubeconfig = {
        "api_version": KUBECONFIG_API_VERSION,
        "kind": KUBECONFIG_KIND,
        "clusters": [
            {
                "name": name,
                "cluster": {
                    "server": cluster.server,
                    "certificate_auth": cluster.certificate_auth,
                    "insecure": cluster.insecure,
                },
            }
            for name, cluster in config.clusters.items()
        ],
        "contexts": [
            {
                "name": name,
                "context": {
                    "cluster": context.cluster,
                    "user": context.user,
                    "namespace": context.namespace,
                },
            }
            for name, context in config.contexts.items()
        ],
        "current-context": config.current_context,
        "users": [
            {
                "name": name,
                "user": {
                    "token": user.token,
                },
            }
            for name, user in config.users.items()
        ],
    }

    return yaml.safe_dump(kubeconfig)
