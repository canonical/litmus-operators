# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Litmus auth integration endpoint wrapper."""

import logging
from typing import Optional

import ops
import pydantic

logger = logging.getLogger()


class DexConfig(pydantic.BaseModel):
    """Configuration model for Dex integration within Litmus."""

    oauth_callback_url: Optional[str] = None
    client_id: Optional[str] = None
    oidc_issuer: Optional[str] = None
    auth_secret_id: Optional[str] = None
    enabled: bool = False


class AuthProviderAppDatabagModel(pydantic.BaseModel):
    """Provider application databag model for the litmus_auth interface."""

    grpc_server_host: str
    grpc_server_port: int
    insecure: bool = False
    dex_config: Optional[DexConfig] = None
    version: int = 0


class AuthRequirerAppDatabagModel(pydantic.BaseModel):
    """Requirer application databag model for the litmus_auth interface."""

    grpc_server_host: str
    grpc_server_port: int
    insecure: bool = False
    version: int = 0


class LitmusAuthDataProvider:
    """Wraps a litmus_auth provider endpoint."""

    def __init__(self, relation: ops.Relation, app: ops.Application):
        self._relation = relation
        self._app = app

    def publish_auth_service_data(
        self,
        grpc_server_host: str,
        grpc_server_port: int,
        insecure: bool = False,
        dex_config: Optional[DexConfig] = None,
    ):
        """Publish litmus auth service data to the requirer."""
        try:
            self._relation.save(
                AuthProviderAppDatabagModel(
                    grpc_server_host=grpc_server_host,
                    grpc_server_port=grpc_server_port,
                    dex_config=dex_config,
                    insecure=insecure,
                )
            )
        except ops.ModelError:
            logger.debug("failed to validate app data; is the relation still being created?")

    def get_requirer_endpoint(self) -> Optional[AuthRequirerAppDatabagModel]:
        """Obtain the requirer's gRPC server endpoint."""
        try:
            return self._relation.load(AuthRequirerAppDatabagModel, self._relation.app)
        except ops.ModelError:
            logger.debug("failed to validate app data; is the relation still being created?")
        except pydantic.ValidationError:
            logger.debug("failed to validate app data; is the relation still settling?")
        return None


class LitmusAuthDataRequirer:
    """Wraps a litmus_auth requirer endpoint."""

    def __init__(self, relation: ops.Relation, app: ops.Application):
        self._relation = relation
        self._app = app

    def publish_endpoint(
        self,
        grpc_server_host: str,
        grpc_server_port: int,
        insecure: bool = False,
    ):
        """Publish the requirer's gRPC server endpoint to the provider."""
        try:
            self._relation.save(
                AuthRequirerAppDatabagModel(
                    grpc_server_host=grpc_server_host,
                    grpc_server_port=grpc_server_port,
                    insecure=insecure,
                )
            )
        except ops.ModelError:
            logger.debug("failed to validate app data; is the relation still being created?")

    def get_auth_service_data(self) -> Optional[AuthProviderAppDatabagModel]:
        """Obtain the litmus auth service data from the provider relation."""
        try:
            return self._relation.load(AuthProviderAppDatabagModel, self._relation.app)
        except ops.ModelError:
            logger.debug("failed to validate app data; is the relation still being created?")
        except pydantic.ValidationError:
            logger.debug("failed to validate app data; is the relation still settling?")
        return None
