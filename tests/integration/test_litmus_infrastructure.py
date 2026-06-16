# Copyright 2025 Canonical Ltd.
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


@pytest.mark.setup
def test_setup_infrastructure(juju: Juju):
    charm_url, channel, resources = _charm_and_channel_and_resources(
        INFRA_APP,
        f"{INFRA_APP.upper()}_CHARM_PATH",
        f"{INFRA_APP.upper()}_CHARM_CHANNEL",
    )

    juju.deploy(
        charm_url,
        app=INFRA_APP,
        channel=channel,
        trust=True,
        resources=resources,
    )

    juju.wait(
        lambda status: all_blocked(status, INFRA_APP),
        error=lambda status: any_error(status, INFRA_APP),
        timeout=1000,
    )


@pytest.mark.setup
def test_integrate_litmus_infrastructure(juju: Juju):
    juju.integrate(INFRA_APP, CHAOSCENTER_APP)
    juju.wait(
        lambda status: all_active(status, CHAOSCENTER_APP, INFRA_APP),
        error=lambda status: any_error(status, CHAOSCENTER_APP, INFRA_APP),
        timeout=1000,
        delay=10,
        successes=3,
    )


@retry(stop=stop_after_attempt(30), wait=wait_fixed(10))
def test_infrastructure_created(juju: Juju, token, project_id):
    # infra name is the juju model where the infra charm is deployed
    expected_infra_name = juju.model
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


def test_remove_integration(juju: Juju):
    juju.remove_relation(INFRA_APP, CHAOSCENTER_APP)
    juju.wait(
        lambda status: (
            all_active(status, CHAOSCENTER_APP) and all_blocked(status, INFRA_APP)
        ),
        error=lambda status: any_error(status, CHAOSCENTER_APP, INFRA_APP),
        timeout=1000,
        delay=10,
        successes=3,
    )


@retry(stop=stop_after_attempt(30), wait=wait_fixed(10))
def test_infrastructure_deleted(juju: Juju, token, project_id):
    expected_infra_name = juju.model
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
    assert len(infras) == 0, f"Infrastructure {expected_infra_name} is not deleted"
