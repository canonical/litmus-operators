# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Litmus auth integration endpoint wrapper."""

import logging
from typing import List, Optional

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

    def __init__(self, relations: List[ops.Relation], app: ops.Application):
        self._relations = relations
        self._app = app

    def publish_auth_service_data(
        self,
        grpc_server_host: str,
        grpc_server_port: int,
        insecure: bool = False,
        dex_config: Optional[DexConfig] = None,
    ):
        """Publish litmus auth service data to the requirers."""
        for relation in self._relations:
            try:
                relation.save(
                    AuthProviderAppDatabagModel(
                        grpc_server_host=grpc_server_host,
                        grpc_server_port=grpc_server_port,
                        dex_config=dex_config,
                        insecure=insecure,
                    ),
                    self._app,
                )
            except ops.ModelError:
                logger.debug("failed to validate app data; is the relation still being created?")
                continue

    def get_requirer_endpoint(self) -> List[AuthRequirerAppDatabagModel]:
        """Obtain the requirers' gRPC server endpoint."""
        out = []
        for relation in sorted(self._relations, key=lambda x: x.id):
            try:
                data = relation.load(AuthRequirerAppDatabagModel, relation.app)
            except ops.ModelError:
                logger.debug("failed to validate app data; is the relation still being created?")
                continue
            except pydantic.ValidationError:
                logger.debug("failed to validate app data; is the relation still settling?")
                continue
            out.append(data)
        return out


class LitmusAuthDataRequirer:
    """Wraps a litmus_auth requirer endpoint."""

    def __init__(self, relations: List[ops.Relation], app: ops.Application):
        self._relations = relations
        self._app = app

    def publish_endpoint(
        self,
        grpc_server_host: str,
        grpc_server_port: int,
        insecure: bool = False,
    ):
        """Publish the requirer's gRPC server endpoint to the providers."""
        for relation in self._relations:
            try:
                relation.save(
                    AuthRequirerAppDatabagModel(
                        grpc_server_host=grpc_server_host,
                        grpc_server_port=grpc_server_port,
                        insecure=insecure,
                    ),
                    self._app,
                )
            except ops.ModelError:
                logger.debug("failed to validate app data; is the relation still being created?")
                continue

    def get_auth_service_data(self) -> List[AuthProviderAppDatabagModel]:
        """Obtain the litmus auth service data from the provider relations."""
        out = []
        for relation in sorted(self._relations, key=lambda x: x.id):
            try:
                data = relation.load(AuthProviderAppDatabagModel, relation.app)
            except ops.ModelError:
                logger.debug("failed to validate app data; is the relation still being created?")
                continue
            except pydantic.ValidationError:
                logger.debug("failed to validate app data; is the relation still settling?")
                continue
            out.append(data)
        return out
