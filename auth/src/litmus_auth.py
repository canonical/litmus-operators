#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Control Litmus Authentication server running in a container under Pebble. Provides a LitmusAuth class."""

import logging

from ops import Container
from ops.pebble import Layer


logger = logging.getLogger(__name__)


class LitmusAuth:
    """Litmus Authentication server workload."""

    name = "authserver"

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
        """Return a Pebble layer for Litmus Auth server."""
        # FIXME: auth server is configured using env variables
        # reconcile based on existing and new env vars
        env = {}
        return Layer(
            {
                "services": {
                    self.name: {
                        "override": "replace",
                        "summary": "litmus auth server layer",
                        # FIXME: after switching to the rock, change the binary to /bin/server
                        "command": "/litmus/server",
                        "startup": "enabled",
                        "environment": env,
                    }
                },
            }
        )
