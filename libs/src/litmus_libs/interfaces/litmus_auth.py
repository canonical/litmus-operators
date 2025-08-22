# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Litmus auth integration endpoint wrapper."""

import logging
from typing import Callable, Dict, List, Optional

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

    dex_oauth_client_secret: Optional[str] = None
    oauth_jwt_secret: Optional[str] = None


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
    """Wraps a litmus_auth provider endpoint."""

    def __init__(
        self,
        relations: List[ops.Relation],
        app: ops.Application,
        secret_getter: Callable[..., ops.Secret],
        secret_setter: Callable[..., ops.Secret],
    ):
        self._relations = relations
        self._app = app
        self._secret_getter = secret_getter
        self._secret_setter = secret_setter

    def _store_dex_config_in_secret(self, dex: DexConfig) -> ops.Secret:
        content = {
            "dex_oauth_client_secret": dex.dex_oauth_client_secret,
            "oauth_jwt_secret": dex.oauth_jwt_secret,
        }
        try:
            secret = self._secret_getter(label=DEX_SECRET_LABEL)
            secret.set_content(content)  # pyright: ignore
            secret.get_content(refresh=True)
            return secret
        except ops.SecretNotFoundError:
            secret = self._secret_setter(
                content=content,
                label=DEX_SECRET_LABEL,
            )
            return secret

    def publish_auth_data(
        self,
        auth_data_config: AuthDataConfig,
    ):
        """Publish litmus auth service data to the requirers."""
        databag_dex_config = None
        dex_secret = None
        if auth_data_config.dex_config:
            dex_secret = self._store_dex_config_in_secret(auth_data_config.dex_config)
            databag_dex_config = _DexConfigDatabagModel(
                **auth_data_config.dex_config.model_dump(),
                auth_secret_id=dex_secret.get_info().id,
            )

        for relation in self._relations:
            try:
                relation.save(
                    AuthProviderAppDatabagModel(
                        grpc_server_host=auth_data_config.grpc_server_host,
                        grpc_server_port=auth_data_config.grpc_server_port,
                        insecure=auth_data_config.insecure,
                        dex_config=databag_dex_config,
                    ),
                    self._app,
                )
            except ops.ModelError:
                logger.debug("failed to validate app data; is the relation still being created?")
                continue

            # grant the requirer access to the secret
            if dex_secret:
                dex_secret.grant(relation)

    def get_requirer_endpoint(self) -> List[Endpoint]:
        """Obtain the requirers' gRPC server endpoint."""
        out: List[Endpoint] = []
        for relation in sorted(self._relations, key=lambda x: x.id):
            try:
                data = relation.load(AuthRequirerAppDatabagModel, relation.app)
            except ops.ModelError:
                logger.debug("failed to validate app data; is the relation still being created?")
                continue
            except pydantic.ValidationError:
                logger.debug("failed to validate app data; is the relation still settling?")
                continue
            out.append(Endpoint(**data.model_dump()))
        return out


class LitmusAuthDataRequirer:
    """Wraps a litmus_auth requirer endpoint."""

    def __init__(
        self,
        relations: List[ops.Relation],
        app: ops.Application,
        secret_getter: Callable[..., ops.Secret],
    ):
        self._relations = relations
        self._app = app
        self._secret_getter = secret_getter

    def _get_dex_secret_content(self, secret_id: str) -> Dict[str, str]:
        dex_secret = self._secret_getter(id=secret_id)
        return dex_secret.get_content()

    def publish_endpoint(
        self,
        endpoint: Endpoint,
    ):
        """Publish the requirer's gRPC server endpoint to the providers."""
        for relation in self._relations:
            try:
                relation.save(
                    AuthRequirerAppDatabagModel(
                        grpc_server_host=endpoint.grpc_server_host,
                        grpc_server_port=endpoint.grpc_server_port,
                        insecure=endpoint.insecure,
                    ),
                    self._app,
                )
            except ops.ModelError:
                logger.debug("failed to validate app data; is the relation still being created?")
                continue

    def get_auth_data(self) -> List[AuthDataConfig]:
        """Obtain the litmus auth service data from the provider relations."""
        out: List[AuthDataConfig] = []
        for relation in sorted(self._relations, key=lambda x: x.id):
            try:
                data = relation.load(AuthProviderAppDatabagModel, relation.app)
            except ops.ModelError:
                logger.debug("failed to validate app data; is the relation still being created?")
                continue
            except pydantic.ValidationError:
                logger.debug("failed to validate app data; is the relation still settling?")
                continue

            dex_config = None
            if data.dex_config:
                dex_dict = data.dex_config.model_dump()
                if secret_id := data.dex_config.auth_secret_id:
                    dex_dict.update(self._get_dex_secret_content(secret_id))
                dex_config = DexConfig(**dex_dict)

            out.append(
                AuthDataConfig(
                    grpc_server_host=data.grpc_server_host,
                    grpc_server_port=data.grpc_server_port,
                    insecure=data.insecure,
                    dex_config=dex_config,
                )
            )
        return out
