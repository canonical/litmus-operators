# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
import shlex
import subprocess
import pytest
from jubilant import Juju, all_blocked, all_active, any_error
from pathlib import Path
from conftest import APP, RESOURCES

MONGO_APP = "mongodb-k8s"

logger = logging.getLogger(__name__)


@pytest.mark.setup
def test_setup(juju: Juju, charm: Path):
    juju.deploy(charm, APP, resources=RESOURCES, trust=True)
    juju.deploy(MONGO_APP)
    juju.integrate(f"{APP}:database", MONGO_APP)

    # TODO: backend server will be blocked because of missing auth server integration
    # https://github.com/canonical/litmus-operators/issues/17
    juju.wait(
        lambda status: all_blocked(status, APP) and all_active(status, MONGO_APP),
        error=any_error,
        timeout=1000,
        delay=10,
        successes=5,
    )


def test_backend_is_running(juju: Juju):
    backend_ip = list(juju.status().get_units(APP).values())[0].public_address
    cmd = (
        f"curl {backend_ip}:8080/query "
        '-H "Content-Type: application/json" '
        '-d \'{"query": "{ listEnvironments(projectID:"test") {environments {name} } }"}\''
    )
    out = subprocess.run(shlex.split(cmd), text=True, capture_output=True)
    assert out.returncode == 0


@pytest.mark.teardown
def test_teardown(juju: Juju):
    juju.remove_application(MONGO_APP)
    juju.wait(
        lambda status: all_blocked(status, APP),
        error=any_error,
        timeout=1000,
        delay=10,
        successes=5,
    )
