# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import logging
import shlex
import subprocess
import pytest
from jubilant import Juju
from tenacity import retry, stop_after_attempt, wait_fixed
from helpers import (
    deploy_control_plane,
    CHAOSCENTER_APP,
    get_unit_ip_address,
    get_login_response,
)

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def token(juju: Juju):
    chaoscenter_ip = get_unit_ip_address(juju, CHAOSCENTER_APP, 0)
    _, out = get_login_response(chaoscenter_ip, 8185, "/auth")
    return json.loads(out)["accessToken"]


@pytest.fixture(scope="module")
def project_id(juju: Juju, token):
    """Fetches the default project ID."""
    chaoscenter_ip = get_unit_ip_address(juju, CHAOSCENTER_APP, 0)
    cmd = (
        "curl -sS -X GET "
        f'-H "Authorization: Bearer {token}" '
        f"http://{chaoscenter_ip}:8185/auth/list_projects"
    )
    out = subprocess.check_output(shlex.split(cmd), text=True)
    return json.loads(out)["data"]["projects"][0]["projectID"]


@pytest.mark.setup
def test_setup_control_plane(juju: Juju):
    deploy_control_plane(juju, wait_for_idle=True)


@retry(stop=stop_after_attempt(30), wait=wait_fixed(10))
def test_default_environment_created(juju: Juju, token, project_id):
    chaoscenter_ip = get_unit_ip_address(juju, CHAOSCENTER_APP, 0)
    expected_env_name = "charmed_litmus"

    query = (
        'query { listEnvironments(projectID: \\"' + project_id + '\\", request: {}) '
        "{ environments { environmentID name } } }"
    )

    cmd = (
        'curl -sS -X POST -H "Content-Type: application/json" '
        f'-H "Authorization: Bearer {token}" '
        f'-d \'{{"query": "{query}"}}\' '
        f"http://{chaoscenter_ip}:8185/api/query"
    )

    out = subprocess.check_output(shlex.split(cmd), text=True)
    data = json.loads(out)

    envs = data["data"]["listEnvironments"]["environments"]
    assert envs[0]["environmentID"] == expected_env_name, f"Environment {expected_env_name} not found in backend"
