#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper for building the K8s config file inside the workload container."""

import base64
import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from lightkube import KubeConfig


logger = logging.getLogger(__name__)


KUBECONFIG_PATH = Path("/.kube/config")


def generate_kubeconfig() -> str:
    config = KubeConfig.from_service_account()

    env = Environment(loader=FileSystemLoader("./src/templates/"))
    template = env.get_template("kubeconfig.yaml.j2")

    kubeconfig = template.render(
        cluster_name=_get_cluster_name(config),
        server_url=_get_server_url(config),
        namespace=_get_namespace(config),
        ca_data=_get_ca_data(config),
        user_token=_get_user_token(config),
    )

    return kubeconfig


def _get_cluster_name(config: KubeConfig) -> str:
    return config.current_context


def _get_server_url(config: KubeConfig) -> str:
    cluster_name = _get_cluster_name(config)
    return config.clusters[cluster_name].server


def _get_namespace(config: KubeConfig) -> str:
    cluster_name = _get_cluster_name(config)
    return config.contexts[cluster_name].namespace


def _get_ca_data(config: KubeConfig) -> str:
    cluster_name = _get_cluster_name(config)
    cert_path = config.clusters[cluster_name].certificate_auth
    with open(cert_path, "rb") as cert_file:
        return base64.b64encode(cert_file.read()).decode()


def _get_user_token(config: KubeConfig) -> str:
    cluster_name = _get_cluster_name(config)
    return config.users[cluster_name].token