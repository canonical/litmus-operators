# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import json
import logging

import pytest
import requests
import urllib3
from jubilant import Juju, all_active
from tenacity import retry, stop_after_attempt, wait_fixed
from helpers import (
    deploy_control_plane,
    BACKEND_APP,
    AUTH_APP,
    CHAOSCENTER_APP,
    SELF_SIGNED_CERTIFICATES_APP,
    get_unit_ip_address,
    get_login_response,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
    deploy_control_plane(juju, with_tls=True, wait_for_idle=True)


@pytest.mark.skip(reason="Removing skips from first to last to find problematic test case")
@retry(stop=stop_after_attempt(30), wait=wait_fixed(10))  # 5 minutes
def test_frontend_is_served_with_ssl(juju: Juju):
    # GIVEN control plane is deployed and TLS is enabled

    # WHEN we call the frontend over https
    chaoscenter_ip = get_unit_ip_address(juju, CHAOSCENTER_APP, 0)
    response = requests.get(
        f"https://{chaoscenter_ip}:8185", verify=False, timeout=30
    )

    # THEN we receive a response that is served by the frontend
    assert "LitmusChaos" in response.text


@pytest.mark.skip(reason="Removing skips from first to last to find problematic test case")
@retry(stop=stop_after_attempt(30), wait=wait_fixed(10))  # 5 minutes
def test_backend_is_served_through_nginx_with_ssl(juju: Juju, token):
    # GIVEN control plane is deployed and TLS is enabled

    # WHEN we call the nginx redirect for backend
    chaoscenter_ip = get_unit_ip_address(juju, CHAOSCENTER_APP, 0)
    query = (
        'mutation { createEnvironment(projectID:"", '
        'request:{environmentID:"test-env-1", name:"My Test Environment", type:NON_PROD}) '
        "{ environmentID name type } }"
    )

    response = requests.post(
        f"https://{chaoscenter_ip}:8185/backend/query",
        json={"query": query},
        headers={"Authorization": f"Bearer {token}"},
        verify=False,
        timeout=30,
    )

    # THEN we receive a response from the backend
    response.raise_for_status()


@pytest.mark.skip(reason="Removing skips from first to last to find problematic test case")
@retry(stop=stop_after_attempt(30), wait=wait_fixed(10))  # 5 minutes
def test_auth_is_served_through_nginx_with_ssl(juju: Juju):
    # GIVEN control plane is deployed and TLS is enabled

    # WHEN we call the nginx redirect for auth server
    chaoscenter_ip = get_unit_ip_address(juju, CHAOSCENTER_APP, 0)
    _, output = get_login_response(
        host=chaoscenter_ip,
        port=8185,
        subpath="/auth",
        use_ssl=True,
    )

    # THEN we receive a response from the auth server
    response_json = json.loads(output)
    assert "accessToken" in response_json, f"No token found in response: {output}"


@pytest.mark.skip(reason="Removing skips from first to last to find problematic test case")
def test_removing_tls_certificates_relation_doesnt_break_the_system(juju: Juju):
    # GIVEN control plane is deployed and TLS is enabled

    # WHEN TLS integration is removed
    juju.remove_relation(AUTH_APP, SELF_SIGNED_CERTIFICATES_APP)
    juju.remove_relation(BACKEND_APP, SELF_SIGNED_CERTIFICATES_APP)
    juju.remove_relation(CHAOSCENTER_APP, SELF_SIGNED_CERTIFICATES_APP)

    # THEN all Litmus control plane applications are still active-idle
    juju.wait(
        lambda status: all_active(status, AUTH_APP, BACKEND_APP, CHAOSCENTER_APP),
        timeout=1000,
        delay=10,
        successes=6,
    )


@pytest.mark.skip(reason="Removing skips from first to last to find problematic test case")
@retry(stop=stop_after_attempt(5), wait=wait_fixed(10))
def test_after_removing_tls_certificates_relation_frontend_is_served_without_ssl(
    juju: Juju,
):
    # GIVEN control plane is deployed and TLS is disabled

    # WHEN we call the frontend over http
    chaoscenter_ip = get_unit_ip_address(juju, CHAOSCENTER_APP, 0)
    response = requests.get(f"http://{chaoscenter_ip}:8185", timeout=30)

    # THEN the frontend is served over http again
    assert "LitmusChaos" in response.text


@pytest.mark.skip(reason="Removing skips from first to last to find problematic test case")
@retry(stop=stop_after_attempt(5), wait=wait_fixed(10))
def test_after_removing_tls_certificates_relation_backend_is_served_without_ssl(
    juju: Juju,
):
    # GIVEN control plane is deployed and TLS is disabled

    # WHEN we call the nginx redirect for backend
    chaoscenter_ip = get_unit_ip_address(juju, CHAOSCENTER_APP, 0)
    _, login_output = get_login_response(
        host=chaoscenter_ip, port=8185, subpath="/auth", use_ssl=False
    )
    access_token = json.loads(login_output)["accessToken"]
    query = (
        'mutation { createEnvironment(projectID:"", '
        'request:{environmentID:"test-env-1", name:"My Test Environment", type:NON_PROD}) '
        "{ environmentID name type } }"
    )

    response = requests.post(
        f"http://{chaoscenter_ip}:8185/backend/query",
        json={"query": query},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )

    # THEN we receive a response from the backend
    response.raise_for_status()


@pytest.mark.skip(reason="Removing skips from first to last to find problematic test case")
@retry(stop=stop_after_attempt(5), wait=wait_fixed(10))
def test_after_removing_tls_certificates_relation_auth_is_served_without_ssl(
    juju: Juju,
):
    # GIVEN control plane is deployed and TLS is disabled

    # WHEN we call the nginx redirect for auth server
    chaoscenter_ip = get_unit_ip_address(juju, CHAOSCENTER_APP, 0)
    _, output = get_login_response(
        host=chaoscenter_ip,
        port=8185,
        subpath="/auth",
        use_ssl=False,
    )

    # THEN we receive a response from the auth server
    response_json = json.loads(output)
    assert "accessToken" in response_json, f"No token found in response: {output}"
