# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for litmusctl.Litmusctl."""

import requests_mock
import pytest

from litmus_client import (
    LitmusClient,
    ChaosProject,
    LitmusAPIException,
    ChaosInfrastructure,
)

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
        # GIVEN: The server rejects login with a 401
        mock_api.post(AUTH_URL, status_code=401)

        # WHEN/THEN: Attempting to login should raise LitmusAPIException
        with pytest.raises(LitmusAPIException, match="Failed to login"):
            client._login()

        assert client._token is None
        assert client._default_project_id is None

    def test_token_persistence(self, client, mock_api):
        # GIVEN: A client that already possesses a valid token
        client._token = "existing-token"

        # WHEN: Getting the auth header
        client._get_auth_header()

        # THEN: No new login request should be triggered
        assert mock_api.call_count == 0

    def test_default_project_id_triggers_login(self, client, mock_api):
        # GIVEN: A client that hasn't logged in yet
        mock_api.post(AUTH_URL, json={"accessToken": "t-1", "projectID": "p-expected"})

        # WHEN: Accessing the default_project_id property
        pid = client.default_project_id

        # THEN: It should trigger a login and return the correct ID
        assert pid == "p-expected"
        assert mock_api.called


class TestRESTMethods:
    def test_list_projects_success(self, client, mock_api):
        # GIVEN: A valid token and a mocked project list response
        client._token = "valid-token"
        payload = {
            "data": {"projects": [{"projectID": "p1", "name": "Default Project"}]}
        }
        mock_api.get(REST_LIST_PROJECTS_URL, json=payload)

        # WHEN: Requesting the list of projects
        projects = client.list_projects()

        # THEN: The response should be a list of ChaosProject objects
        assert len(projects) == 1
        assert isinstance(projects[0], ChaosProject)
        assert projects[0].id == "p1"
        assert projects[0].name == "Default Project"

    def test_rest_calls_failure_raises_exception(self, client, mock_api):
        # GIVEN: The REST endpoint returns a 500 Internal Server Error
        client._token = "valid-token"
        mock_api.get(REST_LIST_PROJECTS_URL, status_code=500)

        # WHEN/THEN: Requesting projects should raise LitmusAPIException
        with pytest.raises(LitmusAPIException):
            client.list_projects()


class TestGraphQLMethods:
    def test_create_environment(self, client, mock_api):
        # GIVEN: A project ID and a desired environment name
        client._token = "valid-token"
        mock_api.post(
            GQL_URL, json={"data": {"createEnvironment": {"environmentID": "env-1"}}}
        )

        # WHEN: Creating an environment
        client.create_environment("proj-1", "production")

        # THEN: Correct variables were sent
        sent_vars = mock_api.request_history[-1].json()["variables"]
        assert sent_vars["request"]["name"] == "production"
        assert sent_vars["request"]["type"] == "NON_PROD"

    def test_gql_error_handling_raises_exception(self, client, mock_api, caplog):
        # GIVEN: A GQL response that returns 200 OK but contains application errors
        client._token = "valid-token"
        error_payload = {"errors": [{"message": "Infrastructure not found"}]}
        mock_api.post(GQL_URL, json=error_payload)

        # WHEN/THEN: Executing a GQL call should raise LitmusAPIException
        with pytest.raises(LitmusAPIException):
            client.get_infrastructure_manifest("infra-123", "proj-1")

    def test_gql_failure_raises_exception(self, client, mock_api):
        # GIVEN: A GQL request that fails with an HTTP 500
        client._token = "valid-token"
        mock_api.post(GQL_URL, status_code=500)

        # WHEN/THEN: It should raise LitmusAPIException
        with pytest.raises(LitmusAPIException):
            client.delete_infrastructure("infra-1", "proj-1")

    def test_register_infrastructure_success(self, client, mock_api):
        # GIVEN: A project ID and registration details
        client._token = "valid-token"
        mock_api.post(
            GQL_URL,
            json={"data": {"registerInfra": {"manifest": "kind: Deployment..."}}},
        )

        # WHEN: Registering infrastructure
        manifest = client.register_infrastructure("my-infra", "litmus", "proj-1")

        # THEN: The manifest should be returned and variables verified
        assert "kind: Deployment" in manifest
        sent_vars = mock_api.request_history[-1].json()["variables"]
        assert sent_vars["projectID"] == "proj-1"
        assert sent_vars["request"]["name"] == "my-infra"
        assert sent_vars["request"]["infraNamespace"] == "litmus"

    def test_get_infrastructure(self, client, mock_api):
        # GIVEN: A mock listInfras response containing the target
        client._token = "valid-token"
        payload = {
            "data": {
                "listInfras": {
                    "infras": [
                        {
                            "infraID": "i-1",
                            "name": "my-infra",
                            "environmentID": "test",
                            "isActive": True,
                            "infraNamespace": "litmus",
                        }
                    ]
                }
            }
        }
        mock_api.post(GQL_URL, json=payload)

        # WHEN: Searching for the infrastructure
        infra = client.get_infrastructure("my-infra", "litmus", "proj-1")

        # THEN: A ChaosInfrastructure object should be returned
        assert isinstance(infra, ChaosInfrastructure)
        assert infra.id == "i-1"
        assert infra.active is True

    def test_get_infrastructure_manifest(self, client, mock_api):
        # GIVEN: A mock response for manifest retrieval
        client._token = "valid-token"
        mock_api.post(GQL_URL, json={"data": {"getInfraManifest": "yaml-content"}})

        # WHEN: Requesting the manifest
        manifest = client.get_infrastructure_manifest("infra-123", "proj-1")

        # THEN: The string content should match
        assert manifest == "yaml-content"
        sent_payload = mock_api.request_history[-1].json()
        assert sent_payload["variables"]["upgrade"] is True

    def test_delete_infrastructure(self, client, mock_api):
        # GIVEN: A successful GQL mock for deletion
        client._token = "valid-token"
        mock_api.post(GQL_URL, json={"data": {"deleteInfra": "Success"}})

        # WHEN: Deleting
        client.delete_infrastructure("infra-1", "proj-1")

        # THEN: One GQL request should have been sent
        assert mock_api.call_count == 1
        sent_vars = mock_api.request_history[-1].json()["variables"]
        assert sent_vars["infraID"] == "infra-1"
