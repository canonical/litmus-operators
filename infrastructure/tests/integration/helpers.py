# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

from jubilant import Juju, all_active, any_error, all_blocked
import requests
from conftest import APP

SELF_SIGNED_CERTIFICATES_APP = "self-signed-certificates"
TEMPO_APP = "tempo"
TEMPO_WORKER_APP = "tempo-worker-all"
S3_APP = "swfs"
TEST_CHANNEL = "dev/edge"


def _get_unit_ip_address(juju: Juju, app_name: str, unit_no: int):
    return juju.status().apps[app_name].units[f"{app_name}/{unit_no}"].address


def deploy_and_integrate_tempo(juju: Juju, tls: bool = False):
    juju.deploy("tempo-coordinator-k8s", TEMPO_APP, channel=TEST_CHANNEL, trust=True)
    juju.deploy("tempo-worker-k8s", TEMPO_WORKER_APP, channel=TEST_CHANNEL, trust=True)
    juju.deploy("seaweedfs-k8s", S3_APP, channel="edge")
    juju.integrate(TEMPO_APP, TEMPO_WORKER_APP)
    juju.integrate(TEMPO_APP, S3_APP)

    if tls:
        juju.deploy(SELF_SIGNED_CERTIFICATES_APP)
        juju.integrate(f"{TEMPO_APP}:certificates", SELF_SIGNED_CERTIFICATES_APP)
        juju.integrate(f"{APP}:receive-ca-certs", SELF_SIGNED_CERTIFICATES_APP)

    juju.integrate(TEMPO_APP, f"{APP}:charm-tracing")

    juju.wait(
        lambda status: (
            all_active(status, TEMPO_APP, TEMPO_WORKER_APP) and all_blocked(status, APP)
        ),
        error=lambda status: any_error(status, TEMPO_APP, TEMPO_WORKER_APP),
        timeout=1000,
        delay=10,
        successes=3,
    )


def assert_charm_traces(juju: Juju, tls: bool = False):
    address = _get_unit_ip_address(juju, TEMPO_APP, 0)
    url = f"http{'s' if tls else ''}://{address}:3200/api/search/tag/juju_application/values"
    response = requests.get(url, verify=False)
    tags = response.json()["tagValues"]
    assert APP in tags
