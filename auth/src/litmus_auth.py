#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Control Litmus Authentication server running in a container under Pebble. Provides a LitmusAuth class."""

import logging

from ops import Container
from ops.pebble import Layer, CheckDict
from typing import Optional, Callable
from litmus_libs import DatabaseConfig, TLSConfigData
from litmus_libs.interfaces.litmus_auth import Endpoint

logger = logging.getLogger(__name__)


class LitmusAuth:
    """Litmus Authentication server workload."""

    name = "auth"
    http_port = 3000
    https_port = 3001
    grpc_port = 3030
    grpc_tls_port = 3031

    def __init__(
        self,
        container: Container,
        tls_cert_path: str,
        tls_key_path: str,
        tls_ca_path: str,
        db_config: Optional[DatabaseConfig],
        tls_config_getter: Callable[[], Optional[TLSConfigData]],
        backend_grpc_endpoint: Optional[Endpoint],
    ):
        self._container = container
        self._tls_cert_path = tls_cert_path
        self._tls_key_path = tls_key_path
        self._tls_ca_path = tls_ca_path
        self._db_config = db_config
        self._tls_config_getter = tls_config_getter
        self._backend_grpc_endpoint = backend_grpc_endpoint

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
        """Return a Pebble layer for Litmus Auth server."""
        tls_config = self._tls_config_getter()
        return Layer(
            {
                "services": {
                    self.name: {
                        "override": "replace",
                        "summary": "litmus auth server layer",
                        "command": "/bin/server",
                        "startup": "enabled",
                        "environment": self._environment_vars(tls_config),
                    }
                },
                "checks": {self.name: self._pebble_check_layer(tls_config)},
            }
        )

    def _pebble_check_layer(self, tls_config: Optional[TLSConfigData]) -> CheckDict:
        return {
            "override": "replace",
            "startup": "enabled",
            "threshold": 3,
            "tcp": {
                "port": self.https_port if tls_config else self.http_port,
            },
        }

    def _environment_vars(self, tls_config: Optional[TLSConfigData]) -> dict:
        env = {
            "ALLOWED_ORIGINS": ".*",
            "REST_PORT": self.http_port,
            "GRPC_PORT": self.grpc_port,
            # default admin credentials to login to the litmus portal for the 1st time
            # Users are prompted to change the password after their first login, so we document
            # this behavior instead of managing state ourselves.
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD": "litmus",
        }
        if db_config := self._db_config:
            env.update(
                {
                    "DB_USER": db_config.username,
                    "DB_PASSWORD": db_config.password,
                    "DB_SERVER": db_config.uris,
                }
            )
        if backend_endpoint := self._backend_grpc_endpoint:
            env.update(
                {
                    "LITMUS_GQL_GRPC_ENDPOINT": backend_endpoint.grpc_server_host,
                    "LITMUS_GQL_GRPC_PORT": backend_endpoint.grpc_server_port,
                }
            )
        if tls_config:
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
    def litmus_auth_ports(self) -> tuple[int, int]:
        if not self._tls_config_getter():
            return self.http_port, self.grpc_port
        return self.https_port, self.grpc_tls_port
