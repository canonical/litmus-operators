# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""High-level client for interacting with the Litmus API."""

from dataclasses import dataclass
import logging
from typing import Any, List

import requests

logger = logging.getLogger(__name__)

LITMUSCTL_BIN = "litmusctl"
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "litmus"


@dataclass
class ChaosProject:
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
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            self._token = resp.json().get("accessToken")
        except Exception as e:
            logger.error("Litmus login failed: %s", e)
            self._token = None

    def _execute_rest(self, method: str, path: str) -> dict[str, Any] | None:
        """Executes a RESTful request."""
        url = f"{self._endpoint}{path}"
        try:
            resp = requests.request(
                method=method, url=url, headers=self._get_auth_header(), timeout=10
            )

            if resp.status_code != 200:
                logger.error(
                    "REST request failed (Status %s): %s", resp.status_code, resp.text
                )
                return None

            data = resp.json()
            if data.get("errors"):
                logger.error(
                    "REST request returned errors: %s", data["errors"][0].get("message")
                )
                return None

            return data.get("data", {})
        except requests.RequestException as e:
            logger.error("REST request failed: %s", e)
            return None

    def _execute_gql(self, query: str, variables: dict | None = None) -> dict | None:
        """Executes a GraphQL request."""
        url = f"{self._endpoint}/api/query"
        payload = {"query": query, "variables": variables or {}}
        try:
            resp = requests.post(
                url=url, json=payload, headers=self._get_auth_header(), timeout=10
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("errors"):
                logger.error("GraphQL error: %s", data["errors"][0]["message"])
                return None

            return data.get("data", {})
        except requests.RequestException as e:
            logger.error("GraphQL request failed: %s", e)
            return None

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
