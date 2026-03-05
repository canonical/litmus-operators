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


@dataclass
class ChaosInfrastructure:
    id: str
    name: str
    environment_id: str
    active: bool


class LitmusAPIException(Exception):
    """Custom exception for LitmusClient errors."""


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
        self._default_project_id: str | None = None

    # We assume a single-project environment where all litmus operations from the charm will occur in this default project.
    @property
    def default_project_id(self) -> str | None:
        """Returns the default project ID."""
        if not self._default_project_id:
            self._login()
        return self._default_project_id

    @property
    def default_env_id(self) -> str:
        """Returns the default environment ID."""
        # TODO: don't hardcode the env ID
        return "test"

    def _get_auth_header(self) -> dict[str, str]:
        """Provides the Bearer token header."""
        if not self._token:
            self._login()
        return {
            "Authorization": f"Bearer {self._token}",
            # Litmus backend middleware fails without a Referer header for some requests
            "Referer": f"{self._endpoint}/",
        }

    def _login(self) -> None:
        """Internal login to fetch the JWT."""
        url = f"{self._endpoint}/auth/login"
        payload = {"username": self._username, "password": self._password}
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            self._token = resp.json().get("accessToken")
            self._default_project_id = resp.json().get("projectID")
        except Exception as e:
            self._token = None
            self._default_project_id = None
            raise LitmusAPIException(
                f"Failed to login to Litmus API at {self._endpoint}: {e}"
            )

    def _execute_rest(self, method: str, path: str) -> dict[str, Any] | None:
        """Executes a RESTful request."""
        url = f"{self._endpoint}{path}"
        try:
            resp = requests.request(
                method=method, url=url, headers=self._get_auth_header(), timeout=10
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
                url=url, json=payload, headers=self._get_auth_header(), timeout=10
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

    def register_infrastructure(
        self, infra_name: str, namespace: str, project_id: str
    ) -> str | None:
        """Registers a new infrastructure in the ChaosCenter and returns its manifest."""
        query = """
        mutation registerInfra($projectID: ID!, $request: RegisterInfraRequest!) {
            registerInfra(projectID: $projectID, request: $request) {
                manifest
            }
        }
        """

        variables = {
            "projectID": project_id,
            "request": {
                "name": infra_name,
                # not providing a description makes a nil pointer exception in the litmus backend
                "description": "",
                "environmentID": self.default_env_id,
                "infrastructureType": "Kubernetes",
                "platformName": "Kubernetes",
                # TODO: link ADR
                "infraScope": "namespace",
                "infraNamespace": namespace,
                "infraNsExists": True,
                "infraSaExists": False,
            },
        }

        data = self._execute_gql(query, variables)
        if not data:
            return None

        return data.get("registerInfra", {}).get("manifest")

    def get_infrastructure(
        self, infrastructure_name: str, namespace: str, project_id: str
    ) -> ChaosInfrastructure | None:
        """Gets infrastructure details by name and namespace. Returns None if not found."""
        query = """
        query listInfras($projectID: ID!, $request: ListInfraRequest!) {
            listInfras(projectID: $projectID, request: $request) {
                infras { infraID name environmentID isActive infraNamespace}
            }
        }
        """

        variables = {
            "projectID": project_id,
            "request": {
                "environmentIDs": [self.default_env_id],
                "filter": {"name": infrastructure_name},
            },
        }

        data = self._execute_gql(query, variables)
        if not data:
            return None

        infras = data.get("listInfras", {}).get("infras", [])
        for infra in infras:
            if infra["infraNamespace"] == namespace:
                return ChaosInfrastructure(
                    id=infra["infraID"],
                    name=infra["name"],
                    environment_id=infra["environmentID"],
                    active=infra["isActive"],
                )
        return None

    def get_infrastructure_manifest(self, infra_id: str, project_id: str) -> str | None:
        """Gets the infrastructure manifest for an existing infrastructure."""
        query = """
        query getInfraManifest($projectID: ID!, $infraID: ID!, $upgrade: Boolean!) {
            getInfraManifest(projectID: $projectID, infraID: $infraID, upgrade: $upgrade)
        }
        """
        variables = {
            "projectID": project_id,
            "infraID": infra_id,
            "upgrade": True,
        }

        data = self._execute_gql(query, variables)
        if not data:
            return None
        return data.get("getInfraManifest")

    def delete_infrastructure(self, infra_id: str, project_id: str):
        """Deletes an infrastructure by ID."""
        query = """
        mutation deleteInfra($projectID: ID!, $infraID: String!) {
            deleteInfra(projectID: $projectID, infraID: $infraID)
        }
        """
        variables = {
            "projectID": project_id,
            "infraID": infra_id,
        }

        self._execute_gql(query, variables)

    def list_projects(self) -> List[ChaosProject]:
        """List all projects accessible to the current account."""
        if data := self._execute_rest("GET", "/auth/list_projects"):
            return [
                ChaosProject(id=p["projectID"], name=p["name"])
                for p in data.get("projects", [])
            ]
        return []

    def create_environment(self, project_id: str, name: str):
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
