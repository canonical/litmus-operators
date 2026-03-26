# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.


"""High-level client for interacting with the Litmus API."""

from dataclasses import dataclass
import logging
from typing import Any
from coordinated_workers.nginx import CA_CERT_PATH
from pathlib import Path
import requests

logger = logging.getLogger(__name__)

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "litmus"
GRAPHQL_QUERIES_PATH = Path(__file__).parent / "graphql"


class LitmusAPIException(Exception):
    """Custom exception for LitmusClient errors."""


@dataclass
class ChaosEnvironment:
    id: str
    name: str


@dataclass
class ChaosInfrastructure:
    id: str
    name: str
    namespace: str
    active: bool


@dataclass
class ChaosExperiment:
    id: str
    infra_id: str


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
        self._default_project = f"{username}-project"

        self._token: str | None = None

        self._ca_bundle = CA_CERT_PATH if endpoint.startswith("https://") else None
        self._session = requests.Session()

    def _load_query(self, query_name: str) -> str:
        return (GRAPHQL_QUERIES_PATH / f"{query_name}.graphql").read_text()

    def _ensure_token(self) -> None:
        if self._token is None:
            self._login()

    def _get_auth_header(self) -> dict[str, str]:
        """Provides the Bearer token header."""
        self._ensure_token()

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
            resp = self._session.post(
                url, json=payload, timeout=10, verify=self._ca_bundle
            )
            resp.raise_for_status()
            self._token = resp.json().get("accessToken")
        except Exception as e:
            self._token = None
            raise LitmusAPIException(
                f"Failed to login to Litmus API at {self._endpoint}: {e}"
            )

    def _execute_rest(
        self, method: str, path: str, payload: dict | None = None
    ) -> dict[str, Any]:
        """Executes a RESTful request."""
        url = f"{self._endpoint}{path}"
        try:
            resp = self._session.request(
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

    def _execute_gql(self, query: str, variables: dict | None = None) -> dict:
        """Executes a GraphQL request."""
        url = f"{self._endpoint}/api/query"
        payload = {"query": query, "variables": variables or {}}
        try:
            resp = self._session.post(
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

    def register_infrastructure(
        self,
        infra_name: str,
        namespace: str,
        project_id: str,
        environment_id: str,
    ) -> str:
        """Registers a new infrastructure in the ChaosCenter and returns its newly created ID.

        Raises LitmusAPIException on failure.
        """
        query = self._load_query("register_infrastructure")

        variables = {
            "projectID": project_id,
            "request": {
                "name": infra_name,
                # not providing a description makes a nil pointer exception in the litmus backend
                "description": "",
                "environmentID": environment_id,
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
        return data.get("registerInfra", {})["infraID"]

    def list_infrastructures(
        self, project_id: str, environment_id: str
    ) -> list[ChaosInfrastructure]:
        """Lists infrastructures in the ChaosCenter.

        Raises LitmusAPIException on failure.
        """
        query = self._load_query("list_infrastructures")

        variables = {
            "projectID": project_id,
            "request": {
                "environmentIDs": [environment_id],
            },
        }

        data = self._execute_gql(query, variables)
        if not data:
            return []

        infras = data.get("listInfras", {}).get("infras", [])
        return [
            ChaosInfrastructure(
                id=infra["infraID"],
                name=infra["name"],
                namespace=infra["infraNamespace"],
                active=infra["isActive"],
            )
            for infra in infras
        ]

    def get_infrastructure_manifest(self, infra_id: str, project_id: str) -> str | None:
        """Gets the infrastructure manifest for an existing infrastructure.

        Raises LitmusAPIException on failure.
        """
        query = self._load_query("get_infrastructure_manifest")

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
        """Deletes an infrastructure by ID.

        Raises LitmusAPIException on failure.
        """
        query = self._load_query("delete_infrastructure")
        variables = {
            "projectID": project_id,
            "infraID": infra_id,
        }

        self._execute_gql(query, variables)

    def list_environments(self, project_id: str) -> list[ChaosEnvironment]:
        """List all environments available in a given project.

        Raises LitmusAPIException on failure.
        """
        query = self._load_query("list_environments")
        variables = {
            "projectID": project_id,
            "request": {
                "environmentIDs": [],
            },
        }

        data = self._execute_gql(query, variables)
        if not data:
            return []

        envs = data.get("listEnvironments", {}).get("environments", [])
        if not envs:
            return []

        return [
            ChaosEnvironment(id=env["environmentID"], name=env["name"]) for env in envs
        ]

    def create_environment(self, project_id: str, name: str):
        """Create a Chaos Environment.

        Raises LitmusAPIException on failure.
        """
        query = self._load_query("create_environment")
        variables = {
            "projectID": project_id,
            "request": {
                "environmentID": name,
                "name": name,
                "description": "",
                "tags": [],
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
            resp = self._session.get(
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

    def get_default_project_id(self) -> str:
        """Get the default project ID for the current user.

        Raises LitmusAPIException on failure.
        """
        data = self._execute_rest("GET", "/auth/list_projects")
        for project in data.get("projects", []):
            if project.get("name") == self._default_project:
                return project.get("projectID")

        raise LitmusAPIException(
            f"Default project '{self._default_project}' not found for user '{self._username}'"
        )

    def list_experiments(self, project_id: str) -> list[ChaosExperiment]:
        """List all chaos experiments in a given project.

        Raises LitmusAPIException on failure.
        """
        query = self._load_query("list_experiments")
        variables = {
            "projectID": project_id,
            "request": {},
        }

        data = self._execute_gql(query, variables)
        return [
            ChaosExperiment(id=exp["experimentID"], infra_id=exp["infra"]["infraID"])
            for exp in data.get("listExperiment", {}).get("experiments", [])
        ]

    def delete_experiment(self, project_id: str, experiment_id: str) -> None:
        """Delete a chaos experiment in a given project by ID.

        Raises LitmusAPIException on failure.
        """
        query = self._load_query("delete_experiment")
        variables = {
            "projectID": project_id,
            "experimentID": experiment_id,
        }

        self._execute_gql(query, variables)
