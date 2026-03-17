# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for Litmus API wrapper."""

import requests
import requests_mock
import pytest

from litmus_client import (
    LitmusClient,
    LitmusAPIException,
    ChaosEnvironment,
    ChaosInfrastructure,
)

# Configuration for mocks
BASE_URL = "http://litmus.local"
AUTH_URL = f"{BASE_URL}/auth/login"
MOCK_REST_PATH = "/mock/endpoint"
MOCK_REST_URL = f"{BASE_URL}{MOCK_REST_PATH}"
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
    def test_rest_calls_success(self, client, mock_api):
        # GIVEN: A valid token and a mocked response
        client._token = "valid-token"
        payload = {"data": {"projects": [{"projectID": "p1", "name": "Default"}]}}
        mock_api.get(MOCK_REST_URL, json=payload)

        # WHEN: calling the mock api endpoint
        data = client._execute_rest("GET", MOCK_REST_PATH)

        # THEN: The response should match the mocked payload
        assert data == {"projects": [{"projectID": "p1", "name": "Default"}]}

    def test_rest_calls_failure_raises_exception(self, client, mock_api):
        # GIVEN: The REST endpoint returns a 500 Internal Server Error
        client._token = "valid-token"
        mock_api.get(MOCK_REST_URL, status_code=500)

        # WHEN/THEN: Requesting projects should raise LitmusAPIException
        with pytest.raises(LitmusAPIException):
            client._execute_rest("GET", MOCK_REST_PATH)

    def test_rest_calls_error_handling_raises_exception(self, client, mock_api):
        # GIVEN: The REST endpoint returns 200 but with an "errors" field
        client._token = "valid-token"
        mock_api.get(
            MOCK_REST_URL,
            json={"errors": [{"message": "something went wrong"}]},
        )

        # WHEN/THEN: Requesting projects should raise LitmusAPIException
        with pytest.raises(LitmusAPIException):
            client._execute_rest(
                "GET",
                MOCK_REST_PATH,
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
            client._execute_gql("mutation {...}")

    def test_gql_failure_raises_exception(self, client, mock_api, caplog):
        # GIVEN: The GQL endpoint raises a network error
        client._token = "valid-token"
        mock_api.post(GQL_URL, exc=requests.exceptions.ConnectionError("timeout"))

        # WHEN/THEN: Executing a GQL call should raise LitmusAPIException
        with pytest.raises(LitmusAPIException):
            client._execute_gql("mutation {...}")

    def test_register_infrastructure_success(self, client, mock_api):
        # GIVEN: A project ID and registration details
        client._token = "valid-token"
        mock_api.post(
            GQL_URL,
            json={"data": {"registerInfra": {"infraID": "47"}}},
        )

        # WHEN: Registering infrastructure
        infra_id = client.register_infrastructure("my-infra", "litmus", "proj-1")

        # THEN: The infraID should be returned and variables verified
        assert infra_id == "47"
        sent_vars = mock_api.request_history[-1].json()["variables"]
        assert sent_vars["projectID"] == "proj-1"
        assert sent_vars["request"]["name"] == "my-infra"
        assert sent_vars["request"]["infraNamespace"] == "litmus"

    def test_list_environments_happy_path(self, client, mock_api):
        # GIVEN: A mock listEnvironments response containing the target
        client._token = "valid-token"
        payload = {
            "data": {
                "listEnvironments": {
                    "environments": [
                        {
                            "name": "test-env",
                            "environmentID": "test-env",
                        }
                    ]
                }
            }
        }
        mock_api.post(GQL_URL, json=payload)

        # WHEN: Searching for the environments
        envs = client.list_environments("proj-1")

        # THEN: A list of ChaosEnvironment objects should be returned
        assert len(envs) == 1
        env = envs[0]
        assert isinstance(env, ChaosEnvironment)
        assert env.id == "test-env"
        assert env.name == "test-env"

    @pytest.mark.parametrize(
        "payload",
        [{"data": None}, {"data": {"listEnvironments": {"environments": None}}}],
    )
    def test_list_environments_empty(self, client, mock_api, payload):
        # GIVEN: A mock listEnvironments response
        client._token = "valid-token"
        mock_api.post(GQL_URL, json=payload)

        # WHEN: Searching for the environments
        envs = client.list_environments("proj-1")

        # THEN: A list of ChaosEnvironment objects should be empty
        assert envs == []

    def test_list_infrastructures(self, client, mock_api):
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
        infras = client.list_infrastructures("proj-1")

        # THEN: A list of ChaosInfrastructure objects should be returned
        assert len(infras) == 1
        infra = infras[0]
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
