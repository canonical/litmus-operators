# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Litmus auth integration endpoint wrapper."""

import logging
from typing import Optional

import ops
import pydantic

logger = logging.getLogger()


class Endpoint(pydantic.BaseModel):
    """Data model representing a server endpoint."""

    grpc_server_host: str
    grpc_server_port: int
    insecure: bool = False


class AuthProviderAppDatabagModel(Endpoint):
    """Provider application databag model for the litmus_auth interface."""

    version: int = 0


class AuthRequirerAppDatabagModel(Endpoint):
    """Requirer application databag model for the litmus_auth interface."""

    version: int = 0


class LitmusAuthDataProvider:
    """Wraps a litmus_auth provider endpoint.

    Usage example:
        ```python
        # In your provider's charm code
        from typing import Optional
        from litmus_libs.interfaces import LitmusAuthDataProvider, Endpoint

        class LitmusAuthProviderCharm(CharmBase):
            def __init__(self, *args):
                super().__init__(*args)
                self._litmus_auth = LitmusAuthDataProvider(
                    self.model.get_relation("litmus-auth"),
                    self.app,
                )

            @property
            def _backend_grpc_endpoint(self) -> Optional[Endpoint]:
                # Get the litmus backend gRPC server endpoint
                return self._litmus_auth.get_backend_grpc_endpoint()

            def _publish_auth_grpc_endpoint(self):
                # Publish the litmus auth server endpoint to the litmus backend
                self._litmus_auth.publish_endpoint(Endpoint(
                    grpc_server_host="my-host",
                    grpc_server_port=80,
                ))
        ```
    """

    def __init__(
        self,
        relation: Optional[ops.Relation],
        app: ops.Application,
    ):
        self._relation = relation
        self._app = app

    def publish_endpoint(
        self,
        endpoint: Endpoint,
    ):
        """Publish this auth server's gRPC endpoint to the backend server."""
        if not self._relation:
            return

        try:
            self._relation.save(
                AuthProviderAppDatabagModel(
                    grpc_server_host=endpoint.grpc_server_host,
                    grpc_server_port=endpoint.grpc_server_port,
                    insecure=endpoint.insecure,
                ),
                self._app,
            )
        except ops.ModelError:
            logger.debug("failed to validate app data; is the relation still being created?")
            return

    def get_backend_grpc_endpoint(self) -> Optional[Endpoint]:
        """Get the backend server's gRPC endpoint."""
        if not self._relation:
            return None
        try:
            data = self._relation.load(AuthRequirerAppDatabagModel, self._relation.app)
        except ops.ModelError:
            logger.debug("failed to validate app data; is the relation still being created?")
            return None
        except pydantic.ValidationError:
            logger.debug("failed to validate app data; is the relation still settling?")
            return None
        return Endpoint(**data.model_dump())


class LitmusAuthDataRequirer:
    """Wraps a litmus_auth requirer endpoint.

    Usage example:
        ```python
        # In your requirer's charm code
        from typing import Optional
        from litmus_libs.interfaces import LitmusAuthDataRequirer, Endpoint

        class LitmusAuthRequirerCharm(CharmBase):
            def __init__(self, *args):
                super().__init__(*args)
                self._litmus_auth = LitmusAuthDataRequirer(
                    self.model.get_relation("litmus-auth"),
                    self.app,
                )

            @property
            def _auth_grpc_endpoint(self) -> Optional[Endpoint]:
                # Get the auth server's gRPC endpoint from the auth server
                return self._litmus_auth.get_auth_grpc_endpoint()

            def _publish_endpoint(self):
                # Publish the litmus backend server's endpoint to the auth server
                self._litmus_auth.publish_endpoint(
                    Endpoint(
                        grpc_server_host="my-host",
                        grpc_server_port=80,
                    )
                )
        ```
    """

    def __init__(
        self,
        relation: Optional[ops.Relation],
        app: ops.Application,
    ):
        self._relation = relation
        self._app = app

    def publish_endpoint(
        self,
        endpoint: Endpoint,
    ):
        """Publish this backend server's gRPC server endpoint to the auth server."""
        if not self._relation:
            return
        try:
            self._relation.save(
                AuthRequirerAppDatabagModel(
                    grpc_server_host=endpoint.grpc_server_host,
                    grpc_server_port=endpoint.grpc_server_port,
                    insecure=endpoint.insecure,
                ),
                self._app,
            )
        except ops.ModelError:
            logger.debug("failed to validate app data; is the relation still being created?")

    def get_auth_grpc_endpoint(self) -> Optional[Endpoint]:
        """Get the auth server's gRPC endpoint."""
        if not self._relation:
            return None
        try:
            data = self._relation.load(AuthProviderAppDatabagModel, self._relation.app)
        except ops.ModelError:
            logger.debug("failed to validate app data; is the relation still being created?")
            return None
        except pydantic.ValidationError:
            logger.debug("failed to validate app data; is the relation still settling?")
            return None

        return Endpoint(**data.model_dump())
