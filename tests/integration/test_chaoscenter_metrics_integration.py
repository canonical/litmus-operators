#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import jubilant
import pytest
import requests
from jubilant import Juju
from tenacity import retry, stop_after_delay
from tenacity import wait_exponential as wexp

from helpers import (
    CHAOSCENTER_APP,
    deploy_control_plane,
    get_unit_ip_address,
)

PROMETHEUS_APP = "prometheus-k8s"
PROMETHEUS_APP_CHANNEL = "1/stable"


@pytest.mark.setup
def test_setup(juju: Juju):
    deploy_control_plane(juju, wait_for_idle=True)

    juju.deploy(
        PROMETHEUS_APP,
        PROMETHEUS_APP,
        channel=PROMETHEUS_APP_CHANNEL,
        trust=True,
    )
    juju.integrate(CHAOSCENTER_APP, PROMETHEUS_APP)

    juju.wait(
        lambda status: jubilant.all_active(status, CHAOSCENTER_APP, PROMETHEUS_APP),
        timeout=1000,
    )


@retry(
    wait=wexp(multiplier=2, min=1, max=30), stop=stop_after_delay(60 * 15), reraise=True
)
def test_metrics_integration(juju: Juju):
    prom_ip = get_unit_ip_address(juju, PROMETHEUS_APP, 0)
    res = requests.get(f"http://{prom_ip}:9090/api/v1/label/juju_application/values")
    assert CHAOSCENTER_APP in res.json()["data"]


@pytest.mark.teardown
def test_teardown(juju: Juju):
    juju.remove_relation(CHAOSCENTER_APP, PROMETHEUS_APP)

    juju.wait(
        lambda status: jubilant.all_active(status, CHAOSCENTER_APP),
        timeout=500,
        delay=60,
    )

    juju.remove_application(CHAOSCENTER_APP)
