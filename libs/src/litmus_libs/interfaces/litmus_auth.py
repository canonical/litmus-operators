# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Litmus auth integration endpoint wrapper."""

import logging
from typing import Dict, Optional

import ops
import pydantic

logger = logging.getLogger()

DEX_SECRET_LABEL = "dex-secret-label"


class _DexConfigBase(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="ignore")

    enabled: bool = False
    oauth_callback_url: Optional[str] = None
    client_id: Optional[str] = None
    oidc_issuer: Optional[str] = None


class _AuthConfigBase(pydantic.BaseModel):
    grpc_server_host: str
    grpc_server_port: int
    insecure: bool = False


class _DexConfigDatabagModel(_DexConfigBase):
    auth_secret_id: Optional[str] = None


class DexConfig(_DexConfigBase):
    """Data model representing the Dex authentication config."""

    # juju secret keys must not contain underscores
    dex_oauth_client_secret: Optional[str] = pydantic.Field(
        default=None, serialization_alias="dex-oauth-client-secret"
    )
    oauth_jwt_secret: Optional[str] = pydantic.Field(
        default=None, serialization_alias="oauth-jwt-secret"
    )


class AuthDataConfig(_AuthConfigBase):
    """Data model for the auth data published by a Litmus auth service provider."""

    dex_config: Optional[DexConfig] = None


class Endpoint(pydantic.BaseModel):
    """Data model representing the requirer server endpoint."""

    grpc_server_host: str
    grpc_server_port: int
    insecure: bool = False


class AuthProviderAppDatabagModel(_AuthConfigBase):
    """Provider application databag model for the litmus_auth interface."""

    dex_config: Optional[_DexConfigDatabagModel] = None
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
        from litmus_libs.interfaces import (
            LitmusAuthDataProvider,
            AuthDataConfig,
            DexConfig,
            Endpoint,
        )

        class LitmusAuthProviderCharm(CharmBase):
            def __init__(self, *args):
                super().__init__(*args)
                self._litmus_auth = LitmusAuthDataProvider(
                    self.model.get_relation("litmus-auth"),
                    self.app,
                    self.model,
                )

            @property
            def _backend_grpc_endpoint(self) -> Optional[Endpoint]:
                # Get the litmus backend gRPC server endpoint
                return self._litmus_auth.get_backend_grpc_endpoint()

            @property
            def _auth_config(self) -> AuthDataConfig:
                # construct the litmus auth data
                return AuthDataConfig(
                    grpc_server_host="my-host",
                    grpc_server_port=80,
                    dex_config=DexConfig(
                        enabled=True,
                        client_id="my-client-id",
                        oauth_callback_url="my-oauth-callback-url",
                    ),
                )

            def _publish_auth_data(self):
                # Publish the litmus auth data to the litmus backend
                self._litmus_auth.publish_auth_data(self._auth_config)
        ```
    """

    def __init__(
        self,
        relation: Optional[ops.Relation],
        app: ops.Application,
        model: ops.Model,
    ):
        self._relation = relation
        self._app = app
        self._model = model

    def _store_dex_config_in_secret(self, dex: Optional[DexConfig]) -> Optional[ops.Secret]:
        if dex is None:
            return None
        content = dex.model_dump(
            include={"dex_oauth_client_secret", "oauth_jwt_secret"},
            by_alias=True,
            exclude_none=True,
        )
        if not content:
            return None
        # update the secret if it already exists
        try:
            secret = self._model.get_secret(label=DEX_SECRET_LABEL)
            secret.set_content(content)
            return secret
        # otherwise create a new one
        except ops.SecretNotFoundError:
            secret = self._app.add_secret(
                content=content,
                label=DEX_SECRET_LABEL,
            )
            return secret

    def publish_auth_data(
        self,
        auth_data: AuthDataConfig,
    ):
        """Publish this auth server's auth data to the backend server."""
        if not self._relation:
            return

        dex_secret = self._store_dex_config_in_secret(auth_data.dex_config)
        try:
            self._relation.save(
                AuthProviderAppDatabagModel(
                    grpc_server_host=auth_data.grpc_server_host,
                    grpc_server_port=auth_data.grpc_server_port,
                    insecure=auth_data.insecure,
                    dex_config=(
                        {
                            **auth_data.dex_config.model_dump(),  # type: ignore
                            **({"auth_secret_id": dex_secret.get_info().id} if dex_secret else {}),
                        }
                        if auth_data.dex_config
                        else None
                    ),
                ),
                self._app,
            )
        except ops.ModelError:
            logger.debug("failed to validate app data; is the relation still being created?")
            return

        # grant the backend server charm access to the secret
        if dex_secret:
            dex_secret.grant(self._relation)

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
        from litmus_libs.interfaces import (
            LitmusAuthDataRequirer,
            AuthDataConfig,
            Endpoint,
        )

        class LitmusAuthRequirerCharm(CharmBase):
            def __init__(self, *args):
                super().__init__(*args)
                self._litmus_auth = LitmusAuthDataRequirer(
                    self.model.get_relation("litmus-auth"),
                    self.app,
                    self.model,
                )

            @property
            def _auth_data(self) -> Optional[AuthDataConfig]:
                # Get the litmus auth data from the auth server
                return self._litmus_auth.get_auth_data()

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
        model: ops.Model,
    ):
        self._relation = relation
        self._app = app
        self._model = model

    def _get_dex_secret_content(self, secret_id: str) -> Dict[str, str]:
        dex_secret = self._model.get_secret(id=secret_id)
        # secret content is cached unless refresh is set to True
        # we want to always fetch the latest content
        content = dex_secret.get_content(refresh=True)
        return {k.replace("-", "_"): v for k, v in content.items()}

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

    def get_auth_data(self) -> Optional[AuthDataConfig]:
        """Get the litmus auth data from the auth server."""
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

        auth_secret_id = data.dex_config.auth_secret_id if data.dex_config else None
        return AuthDataConfig(
            grpc_server_host=data.grpc_server_host,
            grpc_server_port=data.grpc_server_port,
            insecure=data.insecure,
            dex_config=DexConfig(
                **data.dex_config.model_dump(),  # type: ignore
                **(self._get_dex_secret_content(auth_secret_id) if auth_secret_id else {}),
            )
            if data.dex_config
            else None,
        )
