#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Control Litmus Backend server running in a container under Pebble. Provides a LitmusBackend class."""

import logging

from ops import Container
from ops.pebble import Layer
from typing import Optional
from litmus_libs import DatabaseConfig
from litmus_libs.interfaces import Endpoint


logger = logging.getLogger(__name__)


class LitmusBackend:
    """Litmus Backend server workload."""

    name = "litmuschaos-server"
    http_port = 8080
    grpc_port = 8000

    def __init__(
        self,
        container: Container,
        db_config: Optional[DatabaseConfig],
        auth_endpoint: Optional[Endpoint],
    ):
        self._container = container
        self._db_config = db_config
        self._auth_endpoint = auth_endpoint

    def reconcile(self):
        """Unconditional control logic."""
        if self._container.can_connect():
            self._reconcile_workload_config()

    def _reconcile_workload_config(self):
        self._container.add_layer(self.name, self._pebble_layer, combine=True)
        # replan only if the available env var config is sufficient for the workload to run
        if self._db_config:
            self._container.replan()
        else:
            self._container.stop(self.name)

    @property
    def _pebble_layer(self) -> Layer:
        """Return a Pebble layer for Litmus backend server."""
        env = {
            "REST_PORT": self.http_port,
            "GRPC_PORT": self.grpc_port,
            "INFRA_DEPLOYMENTS": '["app=chaos-exporter", "name=chaos-operator", "app=workflow-controller", "app=event-tracker"]',
            "DEFAULT_HUB_BRANCH_NAME": "master",
            "ALLOWED_ORIGINS": ".*",
            "CONTAINER_RUNTIME_EXECUTOR": "k8sapi",
            # TODO: is there a way to provide the version instead of hardcoding it below?
            # https://github.com/canonical/litmus-operators/issues/16
            "WORKFLOW_HELPER_IMAGE_VERSION": "3.20.0",
            "INFRA_COMPATIBLE_VERSIONS": '["3.20.0"]',
            "VERSION": "3.20.0",
            # TODO: use the rocks https://github.com/canonical/litmus-operators/issues/15
            "SUBSCRIBER_IMAGE": "litmuschaos/litmusportal-subscriber:3.20.0",
            "EVENT_TRACKER_IMAGE": "litmuschaos/litmusportal-event-tracker:3.20.0",
            "ARGO_WORKFLOW_CONTROLLER_IMAGE": "litmuschaos/workflow-controller:v3.3.1",
            "ARGO_WORKFLOW_EXECUTOR_IMAGE": "litmuschaos/argoexec:v3.3.1",
            "LITMUS_CHAOS_OPERATOR_IMAGE": "litmuschaos/chaos-operator:3.20.0",
            "LITMUS_CHAOS_RUNNER_IMAGE": "litmuschaos/chaos-runner:3.20.0",
            "LITMUS_CHAOS_EXPORTER_IMAGE": "litmuschaos/chaos-exporter:3.20.0",
        }
        if db_config := self._db_config:
            env.update(
                {
                    "DB_USER": db_config.username,
                    "DB_PASSWORD": db_config.password,
                    "DB_SERVER": db_config.uris,
                }
            )
        if auth_endpoint := self._auth_endpoint:
            env.update(
                {
                    "LITMUS_AUTH_GRPC_ENDPOINT": auth_endpoint.grpc_server_host,
                    "LITMUS_AUTH_GRPC_PORT": auth_endpoint.grpc_server_port,
                }
            )

        return Layer(
            {
                "services": {
                    self.name: {
                        "override": "replace",
                        "summary": "litmus backend server layer",
                        "command": "/bin/server",
                        "startup": "enabled",
                        "environment": env,
                    }
                },
            }
        )
