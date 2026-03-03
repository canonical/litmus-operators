#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper for generating content of the KUBECONFIG file."""

import logging
import yaml
from pathlib import Path

from dataclasses import asdict, dataclass
from lightkube import KubeConfig
from lightkube.config.models import Context, Cluster, User
from lightkube.core.exceptions import ConfigError
from typing import List


logger = logging.getLogger(__name__)


KUBECONFIG_API_VERSION = "v1"
KUBECONFIG_KIND = "Config"
KUBECONFIG_PATH = Path("/.kube/config")


class KubeconfigError(Exception):
    """Exception raised when Kubeconfig can't be generated."""

    def __init__(self, msg: str):
        self.msg = msg


@dataclass
class KubernetesCluster:
    name: str
    cluster: Cluster


@dataclass
class KubernetesContext:
    name: str
    context: Context


@dataclass
class KubernetesUser:
    name: str
    user: User


@dataclass
class Kubeconfig:
    api_version: str
    kind: str
    clusters: List[KubernetesCluster]
    contexts: List[KubernetesContext]
    current_context: str
    users: List[KubernetesUser]


def generate_kubeconfig() -> str:
    try:
        config = KubeConfig.from_service_account()
    except ConfigError as e:
        raise KubeconfigError("Unable to get Kubernetes config from SA.") from e

    if not config.current_context:
        raise KubeconfigError("Unable to get current Kubernetes context.")

    kubeconfig = Kubeconfig(
        api_version=KUBECONFIG_API_VERSION,
        kind=KUBECONFIG_KIND,
        clusters=[
            KubernetesCluster(name, cluster_data) for name, cluster_data in config.clusters.items()
        ],
        contexts=[
            KubernetesContext(name, context_data) for name, context_data in config.contexts.items()
        ],
        current_context=config.current_context,
        users=[KubernetesUser(name, user_data) for name, user_data in config.users.items()],
    )
    kubeconfig = asdict(kubeconfig)
    # Below is needed because the key in the config file is spelled with `-`, but dataclasses
    # do not allow that.
    kubeconfig["current-context"] = kubeconfig.pop("current_context")

    # The KubeConfig object returned by the `KubeConfig.from_service_account()` contains
    # all the fields available in the config file. We remove those that are not set (None)
    # to make the config file clean and easy to ready; otherwise it would be full
    # of `some_key: nil`.
    clean_config = _remove_none(kubeconfig)
    return yaml.safe_dump(clean_config)


def _remove_none(obj):
    """Recursively remove all config fields whose value is None."""
    if isinstance(obj, dict):
        return {
            key: _remove_none(value)
            for key, value in obj.items()
            if value is not None
        }
    elif isinstance(obj, list):
        return [_remove_none(value) for value in obj if value is not None]
    else:
        return obj
