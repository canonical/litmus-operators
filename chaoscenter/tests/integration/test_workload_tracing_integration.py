# !/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

from pathlib import Path
import subprocess
import pytest
import requests
from jubilant import Juju, all_active
from tenacity import retry, stop_after_attempt, wait_fixed
from helpers import CHAOSCENTER_APP, CHAOSCENTER_RESOURCES

CHANNEL = "2/edge"
AUTH_APP = "auth"
BACKEND_APP = "backend"
MONGO_APP = "mongo"
TEMPO_APP = "tempo"
TEMPO_WORKER_APP = "tempo-worker"
S3_APP = "swfs"


def _get_unit_ip_address(juju: Juju, app: str, unit: str = "0"):
    return juju.status().apps[app].units[f"{app}/{unit}"].address


@pytest.mark.setup
def test_setup(juju: Juju, charm: Path):
    def _deploy_control_plane():
        juju.deploy(charm, CHAOSCENTER_APP, resources=CHAOSCENTER_RESOURCES, trust=True)
        juju.deploy("litmus-auth-k8s", AUTH_APP, trust=True, channel=CHANNEL)
        juju.deploy("litmus-backend-k8s", BACKEND_APP, trust=True, channel=CHANNEL)
        juju.deploy("mongodb-k8s", MONGO_APP, trust=True)
        juju.integrate(AUTH_APP, MONGO_APP)
        juju.integrate(BACKEND_APP, MONGO_APP)
        juju.integrate(AUTH_APP, BACKEND_APP)
        juju.integrate(CHAOSCENTER_APP, AUTH_APP)
        juju.integrate(CHAOSCENTER_APP, BACKEND_APP)

    def _deploy_tempo():
        juju.deploy("tempo-coordinator-k8s", TEMPO_APP, channel=CHANNEL, trust=True)
        juju.deploy("tempo-worker-k8s", TEMPO_WORKER_APP, channel=CHANNEL, trust=True)
        juju.deploy("seaweedfs-k8s", S3_APP, channel="edge")
        juju.integrate(TEMPO_APP, TEMPO_WORKER_APP)
        juju.integrate(TEMPO_APP, S3_APP)

    _deploy_control_plane()
    _deploy_tempo()

    juju.integrate(f"{CHAOSCENTER_APP}:workload-tracing", TEMPO_APP)

    juju.wait(all_active, timeout=600, delay=10, successes=6)  # 10m timeout, 1m hold


@retry(stop=stop_after_attempt(5), wait=wait_fixed(10))
def test_chaoscenter_workload_tracing_integration(juju: Juju):
    # GIVEN a litmus chaoscenter integrated with tempo over workload-tracing
    def _trigger_chaoscenter_traces():
        cmd = f"curl -X GET http://{_get_unit_ip_address(juju, CHAOSCENTER_APP)}:8185"
        subprocess.getoutput(cmd)

    # we need to trigger chaoscenter to generate some traces
    _trigger_chaoscenter_traces()

    # WHEN we query the tags for all ingested traces in Tempo
    url = f"http://{_get_unit_ip_address(juju, TEMPO_APP)}:3200/api/search/tag/service.name/values"
    response = requests.get(url)
    tags = response.json()["tagValues"]
    # THEN the litmus chaoscenter has sent some workload traces
    assert f"{CHAOSCENTER_APP}-workload" in tags
