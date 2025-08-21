# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
import pytest
from jubilant import Juju, all_blocked
from pathlib import Path
from helpers import BACKEND_SERVER_APP, BACKEND_SERVER_RESOURCES

logger = logging.getLogger(__name__)


@pytest.mark.setup
def test_deploy_litmus_backend_server(juju: Juju, charm: Path):
    juju.deploy(
        charm, BACKEND_SERVER_APP, resources=BACKEND_SERVER_RESOURCES, trust=True
    )

    # backend server will be blocked because of missing control plane integrations
    juju.wait(
        lambda status: all_blocked(status, BACKEND_SERVER_APP),
        timeout=1000,
        delay=10,
        successes=5,
    )


@pytest.mark.teardown
def test_teardown(juju: Juju):
    juju.remove_application(BACKEND_SERVER_APP)
