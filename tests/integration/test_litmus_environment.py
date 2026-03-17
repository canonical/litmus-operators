# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import logging
import shlex
import subprocess
import pytest
from jubilant import Juju, all_active, any_error, all_blocked
from tenacity import retry, stop_after_attempt, wait_fixed
from helpers import (
    _charm_and_channel_and_resources,
    deploy_control_plane,
    CHAOSCENTER_APP,
    get_unit_ip_address,
    get_login_response,
    INFRA_APP,
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

    query = (
            'query { listInfras(projectID: \\"' + project_id + '\\", '
                                                               'request: {filter: {name: \\"' + expected_infra_name + '\\"}}) '
                                                                                                                      "{ infras { name isActive } } }"
    )

    cmd = (
        'curl -sS -X POST -H "Content-Type: application/json" '
        f'-H "Authorization: Bearer {token}" '
        f'-d \'{{"query": "{query}"}}\' '
        f"http://{chaoscenter_ip}:8185/api/query"
    )

    out = subprocess.check_output(shlex.split(cmd), text=True)
    data = json.loads(out)

    infras = data["data"]["listInfras"]["infras"]
    assert len(infras) > 0, f"Infrastructure {expected_infra_name} not found in backend"
    assert infras[0]["isActive"] is True, "Infrastructure is registered but not active"