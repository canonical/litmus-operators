# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
import pytest
from jubilant import Juju, all_blocked
from pathlib import Path
from helpers import CHAOSCENTER_APP, CHAOSCENTER_RESOURCES

logger = logging.getLogger(__name__)


@pytest.mark.setup
def test_deploy_litmus_auth_server(juju: Juju, charm: Path):
    juju.deploy(charm, CHAOSCENTER_APP, resources=CHAOSCENTER_RESOURCES, trust=True)

    # auth server will be blocked because of missing control plane integrations
    juju.wait(
        lambda status: all_blocked(status, CHAOSCENTER_APP),
        timeout=1000,
        delay=10,
        successes=5,
    )


@pytest.mark.teardown
def test_teardown(juju: Juju):
    juju.remove_application(CHAOSCENTER_APP)
