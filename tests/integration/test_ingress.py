import shlex
import subprocess
import pytest
from helpers import (
    deploy_control_plane,
    CHAOSCENTER_APP,
    AUTH_APP,
    MONGO_APP,
    BACKEND_APP,
    get_unit_ip_address,
)
from jubilant import Juju, all_active, any_error, all_blocked


TRAEFIK_APP = "traefik"


@pytest.mark.setup
def test_setup(juju: Juju):
    deploy_control_plane(juju, wait_for_idle=True)
    juju.deploy("traefik-k8s", channel="latest/edge", app=TRAEFIK_APP, trust=True)
    juju.wait(
        lambda status: all_active(status, TRAEFIK_APP),
        error=lambda status: any_error(status, TRAEFIK_APP),
        timeout=1000,
        delay=10,
        successes=6,
    )


def test_litmus_is_served_over_ingress(juju: Juju):
    # GIVEN a deployment of control plane with traefik

    # WHEN traefik and litmus are related
    juju.integrate(f"{CHAOSCENTER_APP}:ingress", TRAEFIK_APP)

    # THEN it's possible to reach Litmus through the ingress
    juju.wait(
        lambda status: all_active(status, TRAEFIK_APP, CHAOSCENTER_APP),
        error=lambda status: any_error(status, TRAEFIK_APP, CHAOSCENTER_APP),
        timeout=1000,
        delay=10,
        successes=6,
    )

    traefik_ip = get_unit_ip_address(juju, TRAEFIK_APP, 0)
    cmd = f"curl -X GET http://{traefik_ip}:8185"
    result = subprocess.run(shlex.split(cmd), text=True, capture_output=True)

    # THEN we receive a response that is served by the frontend
    assert "LitmusChaos" in result.stdout


@pytest.mark.teardown
def test_teardown(juju: Juju):
    juju.remove_relation(CHAOSCENTER_APP, TRAEFIK_APP)
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
