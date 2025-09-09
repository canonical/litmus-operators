# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
from subprocess import getstatusoutput

import pytest
from jubilant import Juju, all_blocked, all_active, any_error
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_fixed
from conftest import APP, MONGO_APP, RESOURCES
from helpers import get_unit_ip_address

logger = logging.getLogger(__name__)


@pytest.mark.setup
def test_setup(juju: Juju, charm: Path):
    juju.deploy(charm, APP, resources=RESOURCES, trust=True)
    juju.deploy(MONGO_APP, trust=True)
    juju.integrate(f"{APP}:database", MONGO_APP)

    juju.wait(
        lambda status: all_active(status, MONGO_APP) and all_blocked(status, APP),
        error=lambda status: any_error(status, APP),
        timeout=1000,
        delay=10,
        successes=5,
    )


@retry(stop=stop_after_attempt(6), wait=wait_fixed(10))
def test_backend_is_running(juju: Juju):
    backend_ip = get_unit_ip_address(juju, APP, 0)
    cmd = (
        f"curl {backend_ip}:8080/query "
        '-H "Content-Type: application/json" '
        '-d \'{"query": "{ listEnvironments(projectID:"test") {environments {name} } }"}\''
    )
    status, _ = getstatusoutput(cmd)
    assert status == 0


@pytest.mark.teardown
def test_teardown(juju: Juju):
    juju.remove_application(MONGO_APP)
    juju.wait(
        lambda status: all_blocked(status, APP),
        error=lambda status: any_error(status, APP),
        timeout=1000,
        delay=10,
        successes=5,
    )
