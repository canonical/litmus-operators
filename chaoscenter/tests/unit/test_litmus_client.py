# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for Litmus API wrapper."""

import requests
import requests_mock
import pytest

from litmus_client import LitmusClient, ChaosProject, LitmusAPIException

# Configuration for mocks
BASE_URL = "http://litmus.local"
AUTH_URL = f"{BASE_URL}/auth/login"
REST_LIST_PROJECTS_URL = f"{BASE_URL}/auth/list_projects"
GQL_URL = f"{BASE_URL}/api/query"


@pytest.fixture
def client():
    return LitmusClient(endpoint=BASE_URL, username="admin", password="litmus")


@pytest.fixture
def mock_api():
    """Context manager for mocking requests."""
    with requests_mock.Mocker() as m:
        yield m


class TestAuthentication:
    def test_token_lazy_loading(self, client, mock_api):
        # GIVEN: A client with no token and a mocked login endpoint
        mock_api.post(AUTH_URL, json={"accessToken": "new-token"})

        # WHEN: A request is made that requires authentication
        header = client._get_auth_header()

        # THEN: The client should login and return the correct bearer token
        assert client._token == "new-token"
        assert header["Authorization"] == "Bearer new-token"
        assert mock_api.call_count == 1

    def test_failed_login_raises_exception(self, client, mock_api):
        # GIVEN: A client that previously had a token, but the server now rejects login
        client._token = "expired-token"
        mock_api.post(AUTH_URL, status_code=401)

        # WHEN: A login is attempted
        # THEN: Attempting to login should raise LitmusAPIException
        with pytest.raises(LitmusAPIException, match="Failed to login"):
            client._login()

        # AND: The token should be wiped (set to None)
        assert client._token is None

    def test_token_persistence(self, client, mock_api):
        # GIVEN: A client that already possesses a valid token
        client._token = "existing-token"

        # WHEN: Getting the auth header
        client._get_auth_header()

        # THEN: No new login request should be triggered
        assert mock_api.call_count == 0


class TestRESTMethods:
    def test_get_projects_success(self, client, mock_api):
        # GIVEN: A valid token and a mocked project list response
        client._token = "valid-token"
        payload = {"data": {"projects": [{"projectID": "p1", "name": "Default"}]}}
        mock_api.get(REST_LIST_PROJECTS_URL, json=payload)

        # WHEN: Requesting the list of projects
        projects = client.get_projects()

        # THEN: The response should be a list of ChaosProject objects with correct IDs
        assert len(projects) == 1
        assert isinstance(projects[0], ChaosProject)
        assert projects[0].id == "p1"

    def test_rest_calls_failure_raises_exception(self, client, mock_api):
        # GIVEN: The REST endpoint returns a 500 Internal Server Error
        client._token = "valid-token"
        mock_api.get(REST_LIST_PROJECTS_URL, status_code=500)

        # WHEN/THEN: Requesting projects should raise LitmusAPIException
        with pytest.raises(LitmusAPIException):
            client._execute_rest("GET", "/auth/list_projects")

    def test_rest_calls_error_handling_raises_exception(self, client, mock_api):
        # GIVEN: The REST endpoint returns 200 but with an "errors" field
        client._token = "valid-token"
        mock_api.get(
            REST_LIST_PROJECTS_URL,
            json={"errors": [{"message": "something went wrong"}]},
        )

        # WHEN/THEN: Requesting projects should raise LitmusAPIException
        with pytest.raises(LitmusAPIException):
            client._execute_rest(
                "GET",
                "/auth/list_projects",
            )

    def test_user_exists_non_list_response(self, client, mock_api, caplog):
        # GIVEN: The /auth/users endpoint returns a non-list (unexpected format)
        client._token = "valid-token"
        mock_api.get(f"{BASE_URL}/auth/users", json={"unexpected": "dict"})

        # WHEN: Checking if a user exists
        result = client.user_exists("someuser")

        # THEN: The method returns False and a warning is logged
        assert result is False
        assert "Unexpected response format" in caplog.text


class TestGraphQLMethods:
    def test_create_environment(self, client, mock_api):
        # GIVEN: A project ID and a desired environment name
        client._token = "valid-token"
        mock_api.post(
            GQL_URL, json={"data": {"createEnvironment": {"environmentID": "env-1"}}}
        )
        project_id = "proj-123"
        env_name = "production-cluster"

        # WHEN: Creating a chaos environment
        client.create_chaos_environment(project_id, env_name)

        # THEN: The sent GQL variables must match the expected schema
        sent_payload = mock_api.request_history[-1].json()
        assert sent_payload["variables"]["projectID"] == project_id
        assert sent_payload["variables"]["request"]["name"] == env_name

    def test_gql_error_handling_raises_exception(self, client, mock_api, caplog):
        # GIVEN: A GQL response that returns 200 OK but contains application errors
        client._token = "valid-token"
        error_payload = {"errors": [{"message": "Environment name already taken"}]}
        mock_api.post(GQL_URL, json=error_payload)

        # WHEN/THEN: Executing a GQL call should raise LitmusAPIException
        with pytest.raises(LitmusAPIException):
            client._execute_gql("mutation {...}")

    def test_gql_failure_raises_exception(self, client, mock_api, caplog):
        # GIVEN: The GQL endpoint raises a network error
        client._token = "valid-token"
        mock_api.post(GQL_URL, exc=requests.exceptions.ConnectionError("timeout"))

        # WHEN/THEN: Executing a GQL call should raise LitmusAPIException
        with pytest.raises(LitmusAPIException):
            client._execute_gql("mutation {...}")
