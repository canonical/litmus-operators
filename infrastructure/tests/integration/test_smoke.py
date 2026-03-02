# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import logging

import pytest
from jubilant import Juju, all_active, any_error
from pathlib import Path
from conftest import APP

logger = logging.getLogger(__name__)


@pytest.mark.setup
def test_setup(juju: Juju, charm: Path):
    juju.deploy(charm, APP, trust=True)
    juju.wait(
        lambda status: all_active(status, APP),
        error=lambda status: any_error(status, APP),
        timeout=1000,
        delay=10,
        successes=5,
    )


@pytest.mark.teardown
def test_teardown(juju: Juju):
    juju.remove_application(APP)
