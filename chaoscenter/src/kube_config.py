#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper for building the K8s config file inside the workload container."""

import base64
import logging

from jinja2 import Environment, FileSystemLoader
from lightkube import KubeConfig
from typing import Any, Dict


logger = logging.getLogger(__name__)


def generate_kubeconfig() -> str:
    config = KubeConfig.from_service_account()
    config = vars(config)

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


def _get_cluster_name(config: Dict[str, Any]) -> str:
    ctx = vars(config["contexts"][config["current_context"]])
    return getattr(ctx, "cluster", ctx["cluster"])


def _get_server_url(config: Dict[str, Any]) -> str:
    cluster_name = _get_cluster_name(config)
    cluster = vars(config["clusters"][cluster_name])
    return getattr(cluster, "server", cluster["server"])


def _get_namespace(config: Dict[str, Any]) -> str:
    ctx = vars(config["contexts"][config["current_context"]])
    return getattr(ctx, "namespace", ctx["namespace"])


def _get_ca_data(config: Dict[str, Any]) -> str:
    cluster_name = _get_cluster_name(config)
    cluster = vars(config["clusters"][cluster_name])
    cert_path = getattr(cluster, "certificate_auth", cluster["certificate_auth"])
    with open(cert_path, "rb") as cert_file:
        return base64.b64encode(cert_file.read()).decode()


def _get_user_token(config: Dict[str, Any]) -> str:
    cluster_name = _get_cluster_name(config)
    user = vars(config["users"][cluster_name])
    return getattr(user, "token", user["token"])