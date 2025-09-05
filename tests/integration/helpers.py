# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os
import shlex
import subprocess
from typing import Literal
from jubilant import Juju, all_active, any_error
from pytest_jubilant import pack, get_resources
from pathlib import Path

AUTH_APP = "auth"
CHAOSCENTER_APP = "chaoscenter"
BACKEND_APP = "backend"
MONGO_APP = "mongodb"

logger = logging.getLogger(__name__)


def get_unit_ip_address(juju: Juju, app_name: str, unit_no: int):
    """Return a juju unit's IP address."""
    return juju.status().apps[app_name].units[f"{app_name}/{unit_no}"].address


def _charm_and_channel_and_resources(
    role: Literal["auth", "backend"], charm_path_key: str, charm_channel_key: str
):
    """Litmus charms used for integration testing.

    Build once per session and reuse it in all integration tests.
    """
    # deploy charm from charmhub
    if channel_from_env := os.getenv(charm_channel_key):
        charm = f"litmus-{role}-k8s"
        logger.info(f"Using published {charm} charm from {channel_from_env}")
        return charm, channel_from_env, None
    # else deploy from a charm packed locally
    elif path_from_env := os.getenv(charm_path_key):
        charm_path = Path(path_from_env).absolute()
        logger.info("Using local {role} charm: %s", charm_path)
        return (
            charm_path,
            None,
            get_resources(charm_path.parent),
        )
    # else pack the charm
    return pack(Path() / role), None, get_resources(Path().parent / role)


def deploy_control_plane(juju: Juju, wait_for_idle: bool = True):
    for component in (AUTH_APP, BACKEND_APP, CHAOSCENTER_APP):
        charm_url, channel, resources = _charm_and_channel_and_resources(
            component,
            f"{component.upper()}_CHARM_PATH",
            f"{component.upper()}_CHARM_CHANNEL",
        )

        juju.deploy(
            charm_url,
            app=component,
            channel=channel,
            trust=True,
            resources=resources,
        )

    # deploy mongodb
    juju.deploy("mongodb-k8s", app=MONGO_APP, trust=True)

    juju.integrate(f"{AUTH_APP}:database", MONGO_APP)
    juju.integrate(f"{AUTH_APP}:http-api", CHAOSCENTER_APP)
    juju.integrate(f"{BACKEND_APP}:http-api", CHAOSCENTER_APP)
    juju.integrate(f"{BACKEND_APP}:database", MONGO_APP)
    juju.integrate(f"{AUTH_APP}:litmus-auth", f"{BACKEND_APP}:litmus-auth")

    if wait_for_idle:
        logger.info("waiting for the control plane to be active/idle...")
        juju.wait(
            lambda status: all_active(
                status, MONGO_APP, AUTH_APP, BACKEND_APP, CHAOSCENTER_APP
            ),
            error=lambda status: any_error(
                status, AUTH_APP, BACKEND_APP, CHAOSCENTER_APP
            ),
            timeout=1000,
            delay=10,
            successes=6,
        )

def get_login_response(host: str, port: int, subpath: str):
    cmd = (
        'curl -X POST -H "Content-Type: application/json" '
        # TODO: fetch from config options once https://github.com/canonical/litmus-operators/issues/18 is fixed
        '-d \'{"username": "admin", "password": "litmus"}\' '
        f"http://{host}:{port}{subpath}/login"
    )
    return subprocess.run(shlex.split(cmd), text=True, capture_output=True)