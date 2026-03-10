# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""High-level client for interacting with the Litmus API."""

from dataclasses import dataclass
import logging
from typing import Any, List
from coordinated_workers.nginx import CA_CERT_PATH

import requests

logger = logging.getLogger(__name__)

LITMUSCTL_BIN = "litmusctl"
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "litmus"


class LitmusAPIException(Exception):
    """Custom exception for LitmusClient errors."""


@dataclass
class ChaosProject:
    """Litmus project data structure."""

    id: str
    name: str


class LitmusClient:
    """High-level Litmus client using Litmus auth/graphql APIs."""

    def __init__(
        self,
        endpoint: str,
        username: str = DEFAULT_ADMIN_USERNAME,
        password: str = DEFAULT_ADMIN_PASSWORD,
    ):
        self._endpoint = endpoint.rstrip("/")
        self._username = username
        self._password = password
        self._token: str | None = None
        self._ca_bundle = CA_CERT_PATH if endpoint.startswith("https://") else None

    def _get_auth_header(self) -> dict[str, str]:
        """Provides the Bearer token header."""
        if not self._token:
            self._login()
        return {"Authorization": f"Bearer {self._token}"}

    def _login(self) -> None:
        """Internal login to fetch the JWT."""
        url = f"{self._endpoint}/auth/login"
        payload = {"username": self._username, "password": self._password}
        try:
            resp = requests.post(url, json=payload, timeout=10, verify=self._ca_bundle)
            resp.raise_for_status()
            self._token = resp.json().get("accessToken")
        except Exception as e:
            self._token = None
            raise LitmusAPIException(
                f"Failed to login to Litmus API at {self._endpoint}: {e}"
            )

    def _execute_rest(
        self, method: str, path: str, payload: dict | None = None
    ) -> dict[str, Any] | None:
        """Executes a RESTful request."""
        url = f"{self._endpoint}{path}"
        try:
            resp = requests.request(
                method=method,
                url=url,
                headers=self._get_auth_header(),
                json=payload,
                timeout=10,
                verify=self._ca_bundle,
            )

            resp.raise_for_status()

            data = resp.json()
            if data.get("errors"):
                raise LitmusAPIException(
                    f"REST request returned errors: {data['errors'][0].get('message')}"
                )

            return data.get("data", {})
        except requests.RequestException as e:
            raise LitmusAPIException(f"REST request to {url} failed: {e}")

    def _execute_gql(self, query: str, variables: dict | None = None) -> dict | None:
        """Executes a GraphQL request."""
        url = f"{self._endpoint}/api/query"
        payload = {"query": query, "variables": variables or {}}
        try:
            resp = requests.post(
                url=url,
                json=payload,
                headers=self._get_auth_header(),
                timeout=10,
                verify=self._ca_bundle,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("errors"):
                raise LitmusAPIException(
                    f"GraphQL request returned errors: {data['errors'][0].get('message')}"
                )

            return data.get("data", {})
        except requests.RequestException as e:
            raise LitmusAPIException(
                f"GraphQL request for query {query} with vars {variables} failed: {e}"
            )

    def get_projects(self) -> List[ChaosProject]:
        """List all projects accessible to the current account."""
        if data := self._execute_rest("GET", "/auth/list_projects"):
            return [
                ChaosProject(id=p["projectID"], name=p["name"])
                for p in data.get("projects", [])
            ]
        return []

    def create_chaos_environment(self, project_id: str, name: str):
        """Create a Chaos Environment."""
        query = """
        mutation createEnvironment($projectID: ID!, $request: CreateEnvironmentRequest!) {
            createEnvironment(projectID: $projectID, request: $request) {
                environmentID
                name
            }
        }
        """
        variables = {
            "projectID": project_id,
            "request": {
                "environmentID": name,
                "name": name,
                "description": "",
                "tags": [],
                # TODO: make the env type configurable
                "type": "NON_PROD",
            },
        }
        self._execute_gql(query, variables)

    def can_login(self) -> bool:
        """Try to authenticate and return True if credentials are valid."""
        try:
            self._login()
        except LitmusAPIException:
            return False
        return self._token is not None

    def set_password(self, old_password: str, new_password: str) -> None:
        """Change the current user's password.

        Raises LitmusAPIException on failure.
        """
        payload = {
            "username": self._username,
            "OldPassword": old_password,
            "NewPassword": new_password,
        }
        self._execute_rest("POST", "/auth/update/password", payload=payload)

        # Invalidate cached token - must re-login with new password
        self._password = new_password
        self._token = None

    def create_user(
        self, username: str, password: str, name: str = "", email: str = ""
    ) -> None:
        """Create a new user account (requires admin privileges).

        Raises LitmusAPIException on failure.
        """
        payload = {
            "username": username,
            "password": password,
            "name": name or username,
            "email": email,
            "role": "user",
        }
        self._execute_rest("POST", "/auth/create_user", payload=payload)

    def user_exists(self, username: str) -> bool:
        """Return True if a user with the given username exists (requires admin privileges)."""
        url = f"{self._endpoint}/auth/users"
        try:
            resp = requests.get(
                url, headers=self._get_auth_header(), timeout=10, verify=self._ca_bundle
            )
            resp.raise_for_status()
            users = resp.json()
            if isinstance(users, list):
                return any(u.get("username") == username for u in users)
            logger.warning("Unexpected response format from /auth/users")
            return False
        except requests.RequestException as e:
            logger.error("user_exists request failed: %s", e)
            return False
