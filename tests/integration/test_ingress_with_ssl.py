# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import json
import logging
import secrets

import pytest
import requests
import urllib3
from jubilant import Juju
from pytest_jubilant import TempModelFactory
from tenacity import retry, stop_after_attempt, wait_fixed
from helpers import (
    deploy_control_plane,
    CHAOSCENTER_APP,
    TRAEFIK_APP,
    get_unit_ip_address,
    get_login_response,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@pytest.fixture(scope="module")
def temp_model_factory(request):
    """Override default fixture to skip model teardown.

    The default jubilant teardown hangs for TLS-heavy models.
    The model is left behind and cleaned up externally.
    """
    user_model = request.config.getoption("--model")
    if user_model:
        prefix = user_model
        randbits = None
    else:
        prefix = (request.module.__name__.rpartition(".")[-1]).replace("_", "-")
        randbits = secrets.token_hex(4)
    factory = TempModelFactory(
        prefix=prefix, randbits=randbits, check_models_unique=not user_model
    )

    yield factory

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


@retry(stop=stop_after_attempt(30), wait=wait_fixed(10))  # 5 minutes
def test_frontend_is_served_through_traefik_with_ssl(juju: Juju):
    # GIVEN control plane is deployed and TLS is enabled

    # WHEN we call the frontend over https
    traefik_ip = get_unit_ip_address(juju, TRAEFIK_APP, 0)
    response = requests.get(
        f"https://{traefik_ip}:8185", verify=False, timeout=30
    )

    # THEN we receive a response that is served by the frontend
    assert "LitmusChaos" in response.text


@retry(stop=stop_after_attempt(30), wait=wait_fixed(10))  # 5 minutes
def test_backend_is_served_through_traefik_with_ssl(juju: Juju, token):
    # GIVEN control plane is deployed and TLS is enabled

    # WHEN we call the nginx redirect for backend over traefik
    traefik_ip = get_unit_ip_address(juju, TRAEFIK_APP, 0)
    query = (
        'mutation { createEnvironment(projectID:"", '
        'request:{environmentID:"test-env-1", name:"My Test Environment", type:NON_PROD}) '
        "{ environmentID name type } }"
    )

    response = requests.post(
        f"https://{traefik_ip}:8185/backend/query",
        json={"query": query},
        headers={"Authorization": f"Bearer {token}"},
        verify=False,
        timeout=30,
    )

    # THEN we receive a response from the backend
    response.raise_for_status()


@retry(stop=stop_after_attempt(30), wait=wait_fixed(10))  # 5 minutes
def test_auth_is_served_through_traefik_with_ssl(juju: Juju):
    # GIVEN control plane is deployed and TLS is enabled

    # WHEN we call the nginx redirect for auth server
    traefik_ip = get_unit_ip_address(juju, TRAEFIK_APP, 0)
    _, output = get_login_response(
        host=traefik_ip,
        port=8185,
        subpath="/auth",
        use_ssl=True,
    )

    # THEN we receive a response from the auth server
    response_json = json.loads(output)
    assert "accessToken" in response_json, f"No token found in response: {output}"
