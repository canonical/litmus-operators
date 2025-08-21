#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Control Litmus Authentication server running in a container under Pebble. Provides a LitmusAuth class."""

import logging

from ops import Container
from ops.pebble import Layer
from typing import Optional
from models import DatabaseConfig

logger = logging.getLogger(__name__)


class LitmusAuth:
    """Litmus Authentication server workload."""

    name = "authserver"
    http_port = 3000
    grpc_port = 3030

    def __init__(self, container: Container, db_config: Optional[DatabaseConfig]):
        self._container = container
        self._db_config = db_config

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
        env = {
            "ALLOWED_ORIGINS": ".*",
            "REST_PORT": self.http_port,
            "GRPC_PORT": self.grpc_port,
            # default admin credentials to login to the litmus portal for the 1st time
            # TODO: perhaps these should come from config options https://github.com/canonical/litmus-operators/issues/18
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
        return Layer(
            {
                "services": {
                    self.name: {
                        "override": "replace",
                        "summary": "litmus auth server layer",
                        "command": "/bin/server",
                        "startup": "enabled",
                        "environment": env,
                    }
                },
            }
        )
