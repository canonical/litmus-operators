# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
import pytest
from jubilant import Juju, all_blocked, all_active, any_error
from pathlib import Path
from conftest import APP, RESOURCES

MONGO_APP = "mongodb-k8s"


logger = logging.getLogger(__name__)


@pytest.mark.setup
def test_setup(juju: Juju, charm: Path):
    juju.deploy(charm, APP, resources=RESOURCES, trust=True)
    juju.deploy(MONGO_APP, trust=True)
    juju.integrate(f"{APP}:database", MONGO_APP)

    # TODO: assert that the auth charm will be blocked because of missing auth server integration
    # https://github.com/canonical/litmus-operators/issues/17
    juju.wait(
        lambda status: all_active(status, MONGO_APP),
        error=lambda status: any_error(status, APP),
        timeout=1000,
        delay=10,
        successes=5,
    )


# FIXME: add a test


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
