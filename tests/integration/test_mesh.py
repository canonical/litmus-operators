import pytest
from jubilant import Juju, all_active

from tests.integration.helpers import deploy_control_plane


@pytest.fixture(scope="module", autouse=True)
def istio(temp_model_factory):
    istio = temp_model_factory.get_juju(suffix="istio")
    istio.deploy("istio-k8s", "istio", trust=True)
    yield istio


@pytest.fixture(scope="module", autouse=True)
def litmus(temp_model_factory):
    litmus = temp_model_factory.get_juju(suffix="litmus")
    deploy_control_plane(litmus, with_mesh=True, wait_for_idle=False)
    yield litmus


@pytest.mark.setup
def test_setup(litmus: Juju, istio: Juju):
    # wait for idle
    litmus.wait(all_active, timeout=3000)
    istio.wait(all_active, timeout=3000)
