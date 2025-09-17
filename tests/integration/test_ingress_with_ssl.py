# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import json
import logging
import shlex
import subprocess
import pytest
from jubilant import Juju
from helpers import (
    deploy_control_plane,
    CHAOSCENTER_APP,
    TRAEFIK_APP,
    get_unit_ip_address,
    get_login_response,
)

logger = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def token(juju: Juju):
    chaoscenter_ip = get_unit_ip_address(juju, CHAOSCENTER_APP, 0)
    _, out = get_login_response(
        host=chaoscenter_ip, port=8185, subpath="/auth", use_ssl=True
    )
    return json.loads(out)["accessToken"]


@pytest.mark.setup
def test_setup(juju: Juju):
    deploy_control_plane(juju, with_tls=True, with_traefik=True, wait_for_idle=True)


def test_frontend_is_served_with_ssl(juju: Juju):
    # GIVEN control plane is deployed and TLS is enabled

    # WHEN we call the frontend over https
    traefik_ip = get_unit_ip_address(juju, TRAEFIK_APP, 0)
    cmd = f"curl -k -sS -X GET https://{traefik_ip}:8185"
    result = subprocess.getoutput(cmd)

    # THEN we receive a response that is served by the frontend
    assert "LitmusChaos" in result


def test_backend_is_served_through_nginx_with_ssl(juju: Juju, token):
    # GIVEN control plane is deployed and TLS is enabled

    # WHEN we call the nginx redirect for backend iver traefik
    traefik_ip = get_unit_ip_address(juju, TRAEFIK_APP, 0)
    query = (
        'mutation { createEnvironment(projectID:"", '
        'request:{environmentID:"test-env-1", name:"My Test Environment", type:NON_PROD}) '
        "{ environmentID name type } }"
    )

    cmd = (
        'curl -sS -k -X POST -H "Content-Type: application/json" '
        f'-H "Authorization: Bearer {token}" '
        f'-d \'{{"query": "{query}"}}\' '
        f"https://{traefik_ip}:8185/backend/query"
    )

    # THEN we receive a response from the backend
    subprocess.check_call(shlex.split(cmd))


def test_auth_is_served_through_nginx_with_ssl(juju: Juju):
    # GIVEN control plane is deployed and TLS is enabled

    # WHEN we call the nginx redirect for auth server
    traefik_ip = get_unit_ip_address(juju, TRAEFIK_APP, 0)
    returncode, output = get_login_response(
        host=traefik_ip,
        port=8185,
        subpath="/auth",
        use_ssl=True,
    )

    # THEN we receive a response from the auth server
    assert returncode == 0
    response_json = json.loads(output)
    assert "accessToken" in response_json, f"No token found in response: {output}"
