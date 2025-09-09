# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from subprocess import getoutput

import pytest
from jubilant import all_active, all_blocked, any_error, Juju
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_fixed

from conftest import APP, RESOURCES
from helpers import get_unit_ip_address

MONGO_APP = "mongodb-k8s"
SELF_SIGNED_CERTIFICATES_APP = "self-signed-certificates"

logger = logging.getLogger(__name__)


@pytest.mark.setup
def test_setup(juju: Juju, charm: Path):
    juju.deploy(charm, APP, resources=RESOURCES, trust=True)
    juju.deploy(MONGO_APP, trust=True)
    juju.deploy(SELF_SIGNED_CERTIFICATES_APP)
    juju.integrate(f"{APP}:database", MONGO_APP)
    juju.integrate(f"{APP}:tls-certificates", SELF_SIGNED_CERTIFICATES_APP)

    juju.wait(
        lambda status: all_active(status, MONGO_APP, SELF_SIGNED_CERTIFICATES_APP)
        and all_blocked(status, APP),
        error=lambda status: any_error(status, APP),
        timeout=1000,
        delay=10,
        successes=5,
    )


@retry(stop=stop_after_attempt(6), wait=wait_fixed(10))
def test_tls_integration(juju: Juju):
    backend_ip = get_unit_ip_address(juju, APP, 0)
    cmd = f"openssl s_client -connect {backend_ip}:8081"
    out = getoutput(cmd)
    assert f"subject=CN = {APP}" in out
    assert "issuer=CN = self-signed-certificates-operator" in out
