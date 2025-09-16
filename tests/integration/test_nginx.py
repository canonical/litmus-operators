# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import json
import logging
import shlex
import subprocess
import pytest
from jubilant import Juju, all_blocked, any_error
from tenacity import retry, stop_after_attempt, wait_fixed
from helpers import (
    deploy_control_plane,
    BACKEND_APP,
    AUTH_APP,
    MONGO_APP,
    CHAOSCENTER_APP,
    get_unit_ip_address,
    get_login_response,
)

logger = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def token(juju: Juju):
    chaoscenter_ip = get_unit_ip_address(juju, CHAOSCENTER_APP, 0)
    _, out = get_login_response(chaoscenter_ip, 8185, "/auth")
    return json.loads(out)["accessToken"]


@pytest.mark.setup
def test_setup(juju: Juju):
    deploy_control_plane(juju, wait_for_idle=True)


def test_frontend_is_served(juju: Juju):
    # GIVEN control plane is deployed

    # WHEN we call the frontend on its index
    chaoscenter_ip = get_unit_ip_address(juju, CHAOSCENTER_APP, 0)
    cmd = f"curl -X GET http://{chaoscenter_ip}:8185"
    result = subprocess.getoutput(cmd)

    # THEN we receive a response that is served by the frontend
    assert "LitmusChaos" in result


@retry(stop=stop_after_attempt(6), wait=wait_fixed(10))
def test_backend_is_served_through_nginx(juju: Juju, token):
    # GIVEN control plane is deployed

    # WHEN we call the nginx redirect for backend
    chaoscenter_ip = get_unit_ip_address(juju, CHAOSCENTER_APP, 0)
    query = (
        'mutation { createEnvironment(projectID:"", '
        'request:{environmentID:"test-env-1", name:"My Test Environment", type:NON_PROD}) '
        "{ environmentID name type } }"
    )

    cmd = (
        'curl -X POST -H "Content-Type: application/json" '
        f'-H "Authorization: Bearer {token}" '
        f'-d \'{{"query": "{query}"}}\' '
        f"http://{chaoscenter_ip}:8185/backend/query"
    )

    # THEN we receive a response from the backend
    subprocess.check_call(shlex.split(cmd))


@retry(stop=stop_after_attempt(6), wait=wait_fixed(10))
def test_auth_is_served_through_nginx(juju: Juju):
    # GIVEN control plane is deployed

    # WHEN we call the nginx redirect for auth server
    chaoscenter_ip = get_unit_ip_address(juju, CHAOSCENTER_APP, 0)
    returncode, output = get_login_response(chaoscenter_ip, 8185, "/auth")

    # THEN we receive a response from the auth server
    assert returncode == 0
    response_json = json.loads(output)
    assert "accessToken" in response_json, f"No token found in response: {output}"


@pytest.mark.teardown
def test_teardown(juju: Juju):
    juju.remove_relation(AUTH_APP, MONGO_APP)
    juju.remove_relation(BACKEND_APP, MONGO_APP)
    juju.remove_relation(BACKEND_APP, AUTH_APP)

    juju.wait(
        lambda status: all_blocked(status, AUTH_APP, BACKEND_APP),
        error=lambda status: any_error(status, AUTH_APP, BACKEND_APP),
        timeout=1000,
        delay=10,
        successes=6,
    )
