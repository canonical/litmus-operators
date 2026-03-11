# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import logging

import pytest
from jubilant import Juju, all_blocked, any_error
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_fixed
from conftest import APP
from helpers import deploy_and_integrate_tempo, assert_charm_traces

logger = logging.getLogger(__name__)


@pytest.mark.setup
def test_deploy_infra_charm(juju: Juju, charm: Path):
    juju.deploy(charm, APP, trust=True)
    juju.wait(
        lambda status: all_blocked(status, APP),
        error=lambda status: any_error(status, APP),
        timeout=1000,
        delay=10,
        successes=5,
    )


@pytest.mark.setup
def test_deploy_and_integrate_tempo(juju: Juju):
    deploy_and_integrate_tempo(juju, tls=True)


@retry(stop=stop_after_attempt(30), wait=wait_fixed(5))
def test_charm_tracing_with_tls(juju: Juju):
    assert_charm_traces(juju, tls=True)
