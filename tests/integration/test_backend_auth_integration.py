# !/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import shlex
import subprocess
import pytest
from jubilant import Juju, any_error, all_blocked
from tenacity import retry, stop_after_attempt, wait_fixed
from tests.integration.helpers import (
    deploy_control_plane,
    BACKEND_APP,
    AUTH_APP,
    MONGO_APP,
    get_unit_ip_address,
    get_login_response,
)


@pytest.fixture(scope="function")
def token(juju: Juju):
    auth_server_ip = get_unit_ip_address(juju, AUTH_APP, 0)
    _, out = get_login_response(auth_server_ip, 3000, "")
    return json.loads(out)["accessToken"]


@pytest.mark.setup
def test_setup(juju: Juju):
    deploy_control_plane(juju, wait_for_idle=True)


@retry(stop=stop_after_attempt(30), wait=wait_fixed(10))  # 5 minutes
def test_auth_server_login(juju: Juju):
    auth_ip = get_unit_ip_address(juju, AUTH_APP, 0)
    returncode, output = get_login_response(auth_ip, 3000, "")
    assert returncode == 0
    response_json = json.loads(output)
    assert "accessToken" in response_json, f"No token found in response: {output}"


@retry(stop=stop_after_attempt(30), wait=wait_fixed(10))  # 5 minutes
def test_backend_server_create_environment(juju: Juju, token):
    backend_ip = get_unit_ip_address(juju, BACKEND_APP, 0)
    query = (
        'mutation { createEnvironment(projectID:"", '
        'request:{environmentID:"test-env-1", name:"My Test Environment", type:NON_PROD}) '
        "{ environmentID name type } }"
    )

    cmd = (
        'curl -sS -X POST -H "Content-Type: application/json" '
        f'-H "Authorization: Bearer {token}" '
        f'-d \'{{"query": "{query}"}}\' '
        f"http://{backend_ip}:8080/query"
    )

    subprocess.check_call(shlex.split(cmd))


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
