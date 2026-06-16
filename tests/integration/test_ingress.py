import subprocess
import pytest
from helpers import (
    deploy_control_plane,
    CHAOSCENTER_APP,
    TRAEFIK_APP,
    get_unit_ip_address,
)
from jubilant import Juju, all_active, any_error


@pytest.mark.setup
def test_setup(juju: Juju):
    deploy_control_plane(juju, wait_for_idle=True, with_traefik=True)


def test_litmus_is_served_over_ingress(juju: Juju):
    # GIVEN a deployment of control plane with traefik

    # WHEN traefik and litmus are related

    # THEN it's possible to reach Litmus through the ingress
    juju.wait(
        lambda status: all_active(status, TRAEFIK_APP, CHAOSCENTER_APP),
        error=lambda status: any_error(status, TRAEFIK_APP, CHAOSCENTER_APP),
        timeout=1000,
        delay=10,
        successes=6,
    )

    traefik_ip = get_unit_ip_address(juju, TRAEFIK_APP, 0)
    cmd = f"curl -sS -X GET http://{traefik_ip}:8185"
    result = subprocess.getoutput(cmd)

    # THEN we receive a response that is served by the frontend
    assert "LitmusChaos" in result
