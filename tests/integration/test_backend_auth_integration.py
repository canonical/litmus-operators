# !/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import shlex
import subprocess
import pytest
from jubilant import Juju, all_active, any_error, all_blocked
from tenacity import retry, stop_after_attempt, wait_fixed

AUTH_APP = "auth"
BACKEND_APP = "backend"
MONGO_APP = "mongodb-k8s"


def _get_unit_ip_address(juju: Juju, app_name: str, unit_no: int):
    """Return a juju unit's IP address."""
    return juju.status().apps[app_name].units[f"{app_name}/{unit_no}"].address


def _get_login_response(host: str):
    cmd = (
        'curl -X POST -H "Content-Type: application/json" '
        # TODO: fetch from config options once https://github.com/canonical/litmus-operators/issues/18 is fixed
        '-d \'{"username": "admin", "password": "litmus"}\' '
        f"http://{host}:3000/login"
    )
    return subprocess.run(shlex.split(cmd), text=True, capture_output=True)


@pytest.fixture(scope="function")
def token(juju: Juju):
    auth_server_ip = _get_unit_ip_address(juju, AUTH_APP, 0)
    out = _get_login_response(auth_server_ip)
    return json.loads(out.stdout)["accessToken"]


@pytest.mark.setup
def test_setup(juju: Juju, auth_charm_metadata, backend_charm_metadata):
    auth_charm_url, auth_channel, auth_resources = auth_charm_metadata
    backend_charm_url, backend_channel, backend_resources = backend_charm_metadata

    juju.deploy(
        auth_charm_url,
        app=AUTH_APP,
        channel=auth_channel,
        trust=True,
        resources=auth_resources,
    )
    juju.deploy(
        backend_charm_url,
        app=BACKEND_APP,
        channel=backend_channel,
        trust=True,
        resources=backend_resources,
    )
    juju.deploy(MONGO_APP, trust=True)

    juju.integrate(f"{AUTH_APP}:database", MONGO_APP)
    juju.integrate(f"{BACKEND_APP}:database", MONGO_APP)
    juju.integrate(f"{AUTH_APP}:litmus-auth", f"{BACKEND_APP}:litmus-auth")

    juju.wait(
        lambda status: all_active(status, MONGO_APP, AUTH_APP, BACKEND_APP),
        error=lambda status: any_error(status, AUTH_APP, BACKEND_APP),
        timeout=1000,
        delay=10,
        successes=6,
    )


@retry(stop=stop_after_attempt(6), wait=wait_fixed(10))
def test_auth_server_login(juju: Juju):
    auth_ip = _get_unit_ip_address(juju, AUTH_APP, 0)
    response = _get_login_response(auth_ip)
    assert response.returncode == 0
    response_json = json.loads(response.stdout)
    assert "accessToken" in response_json, f"No token found in response: {response}"


@retry(stop=stop_after_attempt(6), wait=wait_fixed(10))
def test_backend_server_create_environment(juju: Juju, token):
    backend_ip = _get_unit_ip_address(juju, BACKEND_APP, 0)
    query = (
        'mutation { createEnvironment(projectID:"", '
        'request:{environmentID:"test-env-1", name:"My Test Environment", type:NON_PROD}) '
        "{ environmentID name type } }"
    )

    cmd = (
        'curl -X POST -H "Content-Type: application/json" '
        f'-H "Authorization: Bearer {token}" '
        f'-d \'{{"query": "{query}"}}\' '
        f"http://{backend_ip}:8080/query"
    )

    out = subprocess.run(shlex.split(cmd), capture_output=True, text=True)
    assert out.returncode == 0


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
