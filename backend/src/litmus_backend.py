#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Control Litmus Backend server running in a container under Pebble. Provides a LitmusBackend class."""

import json
import logging

from ops import Container
from ops.pebble import Layer, CheckDict
from typing import Optional, Callable
from litmus_libs import DatabaseConfig, TLSConfigData, get_litmus_version
from litmus_libs.interfaces.litmus_auth import Endpoint

logger = logging.getLogger(__name__)


class LitmusBackend:
    """Litmus Backend server workload."""

    container_name = "backend"
    layer_name = "backend"
    service_name = "backend"
    liveness_check_name = "backend-up"
    http_port = 8080
    https_port = 8081
    grpc_port = 8000
    grpc_tls_port = 8001
    all_pebble_checks = [liveness_check_name]

    def __init__(
        self,
        container: Container,
        tls_cert_path: str,
        tls_key_path: str,
        tls_ca_path: str,
        db_config: Optional[DatabaseConfig],
        tls_config_getter: Callable[[], Optional[TLSConfigData]],
        auth_grpc_endpoint: Optional[Endpoint],
        frontend_url: Optional[str],
    ):
        self._container = container
        self._tls_cert_path = tls_cert_path
        self._tls_key_path = tls_key_path
        self._tls_ca_path = tls_ca_path
        self._db_config = db_config
        self._tls_config_getter = tls_config_getter
        self._auth_grpc_endpoint = auth_grpc_endpoint
        self._frontend_url = frontend_url
        self._workload_version = get_litmus_version(self._container)

    def reconcile(self):
        """Unconditional control logic."""
        if self._container.can_connect():
            self._reconcile_workload_config()

    def _reconcile_workload_config(self):
        self._container.add_layer(self.layer_name, self._pebble_layer, combine=True)
        # replan only if the available env var config is sufficient for the workload to run
        if self._db_config and self._workload_version:
            self._container.replan()
        else:
            logger.warning(
                "cannot start/restart pebble service: missing database config or workload version.",
            )
            self._container.stop(self.service_name)

    @property
    def _pebble_layer(self) -> Layer:
        """Return a Pebble layer for Litmus backend server."""
        tls_enabled = bool(self._tls_config_getter())
        return Layer(
            {
                "services": {
                    self.service_name: {
                        "override": "replace",
                        "summary": "litmus backend server layer",
                        "command": "/bin/server",
                        "startup": "enabled",
                        "environment": self._environment_vars(tls_enabled),
                    }
                },
                "checks": {
                    self.liveness_check_name: self._pebble_check_layer(tls_enabled)
                },
            }
        )

    def _pebble_check_layer(self, tls_enabled: bool) -> CheckDict:
        return {
            "override": "replace",
            "startup": "enabled",
            "threshold": 3,
            "tcp": {
                "port": self.https_port if tls_enabled else self.http_port,
            },
        }

    def _environment_vars(self, tls_enabled: bool) -> dict:
        workload_version = self._workload_version or ""
        env = {
            "REST_PORT": self.http_port,
            "GRPC_PORT": self.grpc_port,
            "INFRA_DEPLOYMENTS": '["app=chaos-exporter", "name=chaos-operator", "app=workflow-controller", "app=event-tracker"]',
            "DEFAULT_HUB_BRANCH_NAME": "master",  # wokeignore:rule=master
            "ALLOWED_ORIGINS": ".*",
            "CONTAINER_RUNTIME_EXECUTOR": "k8sapi",
            "WORKFLOW_HELPER_IMAGE_VERSION": workload_version,
            # are there other versions we should set along with the current workload version?
            "INFRA_COMPATIBLE_VERSIONS": json.dumps([workload_version]),
            "VERSION": workload_version,
            # TODO: use the rocks https://github.com/canonical/litmus-operators/issues/15
            "SUBSCRIBER_IMAGE": f"litmuschaos/litmusportal-subscriber:{workload_version}",
            "EVENT_TRACKER_IMAGE": f"litmuschaos/litmusportal-event-tracker:{workload_version}",
            "ARGO_WORKFLOW_CONTROLLER_IMAGE": "litmuschaos/workflow-controller:v3.3.1",
            "ARGO_WORKFLOW_EXECUTOR_IMAGE": "litmuschaos/argoexec:v3.3.1",
            "LITMUS_CHAOS_OPERATOR_IMAGE": f"litmuschaos/chaos-operator:{workload_version}",
            "LITMUS_CHAOS_RUNNER_IMAGE": f"litmuschaos/chaos-runner:{workload_version}",
            "LITMUS_CHAOS_EXPORTER_IMAGE": f"litmuschaos/chaos-exporter:{workload_version}",
        }

        if db_config := self._db_config:
            env.update(
                {
                    "DB_USER": db_config.username,
                    "DB_PASSWORD": db_config.password,
                    "DB_SERVER": db_config.uris,
                }
            )
        if auth_endpoint := self._auth_grpc_endpoint:
            env.update(
                {
                    "LITMUS_AUTH_GRPC_ENDPOINT": auth_endpoint.grpc_server_host,
                    "LITMUS_AUTH_GRPC_PORT": auth_endpoint.grpc_server_port,
                }
            )
        if frontend_url := self._frontend_url:
            env.update(
                {
                    "CHAOS_CENTER_UI_ENDPOINT": frontend_url,
                }
            )
        if tls_enabled:
            env.update(
                {
                    "ENABLE_INTERNAL_TLS": "true",
                    "REST_PORT": self.https_port,
                    "GRPC_PORT": self.grpc_tls_port,
                    "TLS_CERT_PATH": self._tls_cert_path,
                    "TLS_KEY_PATH": self._tls_key_path,
                    "CA_CERT_TLS_PATH": self._tls_ca_path,
                }
            )

        return env

    @property
    def litmus_backend_ports(self) -> tuple[int, int]:
        if not self._tls_config_getter():
            return self.http_port, self.grpc_port
        return self.https_port, self.grpc_tls_port
