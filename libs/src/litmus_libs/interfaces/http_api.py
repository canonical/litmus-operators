# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Litmus auth integration endpoint wrapper."""

from typing import Optional

import pydantic

from .base import BaseVersionedModel, SimpleEndpointWrapper


class AuthApiProviderAppDatabagModelV0(BaseVersionedModel):
    """Auth API provider application databag model."""

    version: int = 0
    endpoint: pydantic.HttpUrl


class BackendApiProviderAppDatabagModelV0(BaseVersionedModel):
    """Backend API provider application databag model."""

    version: int = 0
    endpoint: pydantic.HttpUrl


class BackendApiRequirerAppDatabagModelV0(BaseVersionedModel):
    """Backend API requirer application databag model."""

    version: int = 0
    endpoint: pydantic.HttpUrl


class LitmusBackendApiProvider(SimpleEndpointWrapper):
    """Wraps a litmus_backend_http_api provider endpoint.

    Usage:

    ```python
    from typing import Optional
    from litmus_libs.interfaces import LitmusBackendApiProvider

    class LitmusBackendHttpProviderCharm(CharmBase):
        def __init__(self, *args):
            super().__init__(*args)
            self._litmus_backend_api = LitmusBackendApiProvider(
                self.model.get_relation("litmus-backend-http-api"),
                self.app,
            )

        @property
        def _backend_http_api_endpoint(self) -> Optional[str]:
            # Publish the litmus backend http API server endpoint
            url = f"https://{socket.getfqdn()}:1234" # for example
            return self._litmus_backend_api.publish_endpoint(url)

        @property
        def _frontend_url(self):
            # obtain frontend URL from frontend component
            return self._litmus_backend_api.frontend_url()
    ```
    """

    @property
    def frontend_endpoint(self) -> Optional[str]:
        """Retrieve the url of the frontend component."""
        datamodel = self._get(BackendApiRequirerAppDatabagModelV0)
        if not datamodel:
            return None
        return str(datamodel.endpoint)

    def publish_endpoint(
        self,
        endpoint: str,
    ):
        """Publish this backend server's HTTP endpoint to the chaoscenter component."""
        self._set(
            model=BackendApiProviderAppDatabagModelV0,
            data={"endpoint": pydantic.HttpUrl(endpoint)},
        )


class LitmusBackendApiRequirer(SimpleEndpointWrapper):
    """Wraps a litmus_backend_http_api requirer endpoint.

    Usage:

    ```python
    from typing import Optional
    from litmus_libs.interfaces import LitmusBackendApiRequirer

    class LitmusBackendHttpRequirerCharm(CharmBase):
        def __init__(self, *args):
            super().__init__(*args)
            self._litmus_backend_api = LitmusBackendApiRequirer(
                self.model.get_relation("litmus-backend-http-api"),
                self.app,
            )

        @property
        def _backend_http_api_endpoint(self) -> Optional[str]:
            # Get the litmus backend http API server endpoint
            return self._litmus_backend_api.endpoint
    ```
    """

    @property
    def backend_endpoint(self) -> Optional[str]:
        """Fetch the backend API endpoint from relation data."""
        datamodel = self._get(BackendApiProviderAppDatabagModelV0)
        if not datamodel:
            return None
        return str(datamodel.endpoint)

    def publish_endpoint(
        self,
        endpoint: str,
    ):
        """Publish this frontend's HTTP endpoint to the backend component."""
        self._set(
            model=BackendApiRequirerAppDatabagModelV0,
            data={"endpoint": pydantic.HttpUrl(endpoint)},
        )


class LitmusAuthApiProvider(SimpleEndpointWrapper):
    """Wraps a litmus_auth_http_api provider endpoint.

    Usage:

    ```python
    from typing import Optional
    from litmus_libs.interfaces import LitmusAuthApiProvider

    class LitmusAuthHttpProviderCharm(CharmBase):
        def __init__(self, *args):
            super().__init__(*args)
            self._litmus_auth_api = LitmusAuthApiProvider(
                self.model.get_relation("litmus-auth-http-api"),
                self.app,
            )

        @property
        def _auth_http_api_endpoint(self) -> Optional[str]:
            # Publish the litmus auth http API server endpoint
            url = f"https://{socket.getfqdn()}:1234" # for example
            return self._litmus_auth_api.publish_endpoint(url)
    ```
    """

    def publish_endpoint(
        self,
        endpoint: str,
    ):
        """Publish this auth server's HTTP endpoint to the chaoscenter component."""
        self._set(
            model=AuthApiProviderAppDatabagModelV0, data={"endpoint": pydantic.HttpUrl(endpoint)}
        )


class LitmusAuthApiRequirer(SimpleEndpointWrapper):
    """Wraps a litmus_auth_http_api requirer endpoint.

    Usage:

    ```python
    from typing import Optional
    from litmus_libs.interfaces import LitmusAuthApiRequirer

    class LitmusAuthHttpRequirerCharm(CharmBase):
        def __init__(self, *args):
            super().__init__(*args)
            self._litmus_auth_api = LitmusAuthApiRequirer(
                self.model.get_relation("litmus-auth-http-api"),
                self.app,
            )

        @property
        def _auth_http_api_endpoint(self) -> Optional[str]:
            # Get the litmus auth http API server endpoint
            return self._litmus_auth_api.endpoint
    ```
    """

    @property
    def auth_endpoint(self) -> Optional[str]:
        """Fetch the auth API endpoint from relation data."""
        datamodel = self._get(AuthApiProviderAppDatabagModelV0)
        if not datamodel:
            return None
        return str(datamodel.endpoint)
