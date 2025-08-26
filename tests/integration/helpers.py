# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Literal

import jubilant
from jubilant import Juju
from pytest_jubilant import pack, get_resources

# Application names used uniformly across the tests
AUTH_APP = "auth"
BACKEND_APP = "backend"
CHAOSCENTER_APP = "chaoscenter"
MONGO_APP = "mongodb"

logger = logging.getLogger(__name__)


def get_unit_ip_address(juju: Juju, app_name: str, unit_no: int):
    """Return a juju unit's IP address."""
    return juju.status().apps[app_name].units[f"{app_name}/{unit_no}"].address


def charm_and_channel_and_resources(
    component: Literal[BACKEND_APP, AUTH_APP, CHAOSCENTER_APP], charm_path_key: str, charm_channel_key: str
):
    """Pyrosocope coordinator or worker charm used for integration testing.

    Build once per session and reuse it in all integration tests to save some minutes/hours.
    """
    # deploy charm from charmhub
    if channel_from_env := os.getenv(charm_channel_key):
        charm = f"litmus-{component}-k8s"
        logger.info(f"Using published {charm} charm from {channel_from_env}")
        return charm, channel_from_env, None
    # else deploy from a charm packed locally
    elif path_from_env := os.getenv(charm_path_key):
        charm_path = Path(path_from_env).absolute()
        if not charm_path.exists():
            raise FileNotFoundError(charm_path)
        logger.info("Using local %s charm: %s", component, charm_path)
        return (
            charm_path,
            None,
            get_resources(charm_path.parent),
        )
    # else try to pack the charm
    for _ in range(3):
        logger.info(f"packing litmus {component} charm...")
        try:
            pth = pack(Path() / component)
        except subprocess.CalledProcessError:
            logger.warning(f"Failed to build litmus {component}. Trying again!")
            continue
        os.environ[charm_path_key] = str(pth)
        return pth, None, get_resources(Path().parent / component)
    raise subprocess.CalledProcessError


def deploy_cluster(
    juju: Juju, wait_for_active: bool = False
):
    """Deploy a full litmus cluster."""
    for component in (CHAOSCENTER_APP, AUTH_APP, BACKEND_APP):
        charm_url, channel, resources = charm_and_channel_and_resources(
            component, f"{component.upper()}_CHARM_PATH", f"{component.upper()}_CHARM_CHANNEL"
        )
        juju.deploy(
            charm_url,
            app=component,
            channel=channel,
            trust=True,
            resources=resources,
        )

    deploy_mongo(juju)
    juju.integrate(AUTH_APP, MONGO_APP)
    juju.integrate(BACKEND_APP, MONGO_APP)
    juju.integrate(AUTH_APP+":http-api", CHAOSCENTER_APP+":auth-http-api")
    juju.integrate(BACKEND_APP+":http-api", CHAOSCENTER_APP+":backend-http-api")
    if wait_for_active:
        juju.wait(
            lambda s: jubilant.all_active(s, CHAOSCENTER_APP, AUTH_APP, BACKEND_APP, MONGO_APP)
        )


def deploy_mongo(juju: Juju):
    juju.deploy("mongodb-k8s", MONGO_APP, channel="6/stable")