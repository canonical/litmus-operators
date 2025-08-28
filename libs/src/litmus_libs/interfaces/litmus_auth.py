# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Litmus auth integration endpoint wrapper."""

import logging
from dataclasses import asdict, dataclass
from typing import Optional

import pydantic

from .base import BaseVersionedModel, SimpleEndpointWrapper

logger = logging.getLogger()


@dataclass
class Endpoint:
    """User-facing data model representing a gRPC server endpoint."""

    grpc_server_host: str
    grpc_server_port: int
    insecure: bool = False


class _EndpointModel(pydantic.BaseModel):
    grpc_server_host: str
    grpc_server_port: int
    insecure: bool = False


class _LitmusAuthProviderAppDatabagModelV0(BaseVersionedModel, _EndpointModel):
    """V0 provider application databag model for the litmus_auth interface."""

    version: int = 0


class _LitmusAuthRequirerAppDatabagModelV0(BaseVersionedModel, _EndpointModel):
    """V0 requirer application databag model for the litmus_auth interface."""

    version: int = 0


class LitmusAuthProvider(SimpleEndpointWrapper):
    """Wraps a litmus_auth provider endpoint.

    Usage example:
        ```python
        # In your provider's charm code
        from typing import Optional
        from litmus_libs.interfaces.limtus_auth import LitmusAuthProvider, Endpoint

        class LitmusAuthProviderCharm(CharmBase):
            def __init__(self, *args):
                super().__init__(*args)
                self._litmus_auth = LitmusAuthProvider(
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

    def publish_endpoint(
        self,
        endpoint: Endpoint,
    ):
        """Publish this auth server's gRPC endpoint to the backend server.

        Raises:
            pydantic.ValidationError: If the provided data does not conform to the expected schema.
        """
        self._set(_LitmusAuthProviderAppDatabagModelV0, asdict(endpoint))

    def get_backend_grpc_endpoint(self) -> Optional[Endpoint]:
        """Get the backend server's gRPC endpoint.

        Raises:
            VersionMismatchError: If the schema version in the relation data
            is not the one supported by this library version.
        """
        data = self._get(_LitmusAuthRequirerAppDatabagModelV0)
        # wrap the data in a user-facing model (Endpoint) to hide internal fields like `version`
        return (
            Endpoint(
                grpc_server_host=data.grpc_server_host,
                grpc_server_port=data.grpc_server_port,
                insecure=data.insecure,
            )
            if data
            else None
        )


class LitmusAuthRequirer(SimpleEndpointWrapper):
    """Wraps a litmus_auth requirer endpoint.

    Usage example:
        ```python
        # In your requirer's charm code
        from typing import Optional
        from litmus_libs.interfaces.limtus_auth import LitmusAuthRequirer, Endpoint

        class LitmusAuthRequirerCharm(CharmBase):
            def __init__(self, *args):
                super().__init__(*args)
                self._litmus_auth = LitmusAuthRequirer(
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

    def publish_endpoint(
        self,
        endpoint: Endpoint,
    ):
        """Publish this backend server's gRPC server endpoint to the auth server.

        Raises:
            pydantic.ValidationError: If the provided data does not conform to the expected schema.
        """
        self._set(_LitmusAuthRequirerAppDatabagModelV0, asdict(endpoint))

    def get_auth_grpc_endpoint(self) -> Optional[Endpoint]:
        """Get the auth server's gRPC endpoint.

        Raises:
            VersionMismatchError: If the schema version in the relation data
            is not supported by this library version.
        """
        data = self._get(_LitmusAuthProviderAppDatabagModelV0)
        # wrap the data in a user-facing model (Endpoint) to hide internal fields like `version`
        return (
            Endpoint(
                grpc_server_host=data.grpc_server_host,
                grpc_server_port=data.grpc_server_port,
                insecure=data.insecure,
            )
            if data
            else None
        )
