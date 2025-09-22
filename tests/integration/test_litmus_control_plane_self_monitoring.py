# !/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import subprocess
import pytest
import requests
from jubilant import Juju, all_active
from tenacity import retry, stop_after_attempt, wait_fixed
from tests.integration.helpers import (
    CHAOSCENTER_APP,
    deploy_control_plane,
    COMPONENTS,
    get_unit_ip_address,
    deploy_self_monitoring_stack,
    LOKI_APP,
    TEMPO_APP,
)


@pytest.mark.setup
def test_setup(juju: Juju):
    deploy_control_plane(juju, wait_for_idle=False)
    deploy_self_monitoring_stack(juju)

    for component in COMPONENTS:
        juju.integrate(TEMPO_APP, f"{component}:charm-tracing")
        juju.integrate(LOKI_APP, f"{component}:logging")

    juju.wait(all_active, timeout=600, delay=10, successes=6)  # 10m timeout, 1m hold


@retry(stop=stop_after_attempt(30), wait=wait_fixed(5))
def test_charm_tracing_integration(juju: Juju):
    # GIVEN a litmus cluster integrated with tempo over charm-tracing
    address = get_unit_ip_address(juju, TEMPO_APP, 0)
    # WHEN we query the tags for all ingested traces in Tempo
    url = f"http://{address}:3200/api/search/tag/juju_application/values"
    response = requests.get(url)
    tags = response.json()["tagValues"]
    # THEN each litmus charm has sent some charm traces
    for component in COMPONENTS:
        assert component in tags


@retry(stop=stop_after_attempt(5), wait=wait_fixed(10))
def test_logging_integration(juju: Juju):
    # GIVEN a litmus cluster integrated with loki over logging
    def _trigger_chaoscenter_logs():
        cmd = f"curl -X GET http://{get_unit_ip_address(juju, CHAOSCENTER_APP, 0)}:8185"
        subprocess.getoutput(cmd)

    # we need to trigger chaoscenter to generate some logs
    _trigger_chaoscenter_logs()

    # WHEN we query the logs for each component
    address = get_unit_ip_address(juju, LOKI_APP, 0)
    # Use query_range for a longer default time interval
    url = f"http://{address}:3100/loki/api/v1/query_range"
    for component in COMPONENTS:
        query = f'{{juju_application="{component}"}}'
        params = {"query": query}
        # THEN we should get a successful response and at least one result
        try:
            response = requests.get(url, params=params)
            data = response.json()
            assert data["status"] == "success", (
                f"Log query failed for component '{component}'"
            )
            assert len(data["data"]["result"]) > 0, (
                f"No logs found for component '{component}'"
            )
        except requests.exceptions.RequestException as e:
            assert False, f"Request to Loki failed for component '{component}': {e}"
