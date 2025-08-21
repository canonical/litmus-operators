#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Control Litmus Backend server running in a container under Pebble. Provides a LitmusBackend class."""

import logging

from ops import Container
from ops.pebble import Layer


logger = logging.getLogger(__name__)


class LitmusBackend:
    """Litmus Backend server workload."""

    name = "litmuschaos-server"
    http_port = 8080

    def __init__(self, container: Container):
        self._container = container

    def reconcile(self):
        """Unconditional control logic."""
        if self._container.can_connect():
            self._reconcile_workload_config()

    def _reconcile_workload_config(self):
        layer = self._pebble_layer
        services = layer.services.keys()
        self._container.add_layer(self.name, layer, combine=True)
        # FIXME: only restart if we have a valid config else stop the service
        # if VALID_CONFIG
        # self._container.restart(*services)
        # else
        self._container.stop(*services)

    @property
    def _pebble_layer(self) -> Layer:
        """Return a Pebble layer for Litmus backend server."""
        # FIXME: Backend server is configured using env variables
        # reconcile based on existing and new env vars
        env = {}
        return Layer(
            {
                "services": {
                    self.name: {
                        "override": "replace",
                        "summary": "litmus backend server layer",
                        # FIXME: after switching to the rock, change the binary to /bin/server
                        "command": "server",
                        "startup": "enabled",
                        "environment": env,
                    }
                },
            }
        )
