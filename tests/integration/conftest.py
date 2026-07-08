# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import logging

from pytest import fixture
from pytest_jubilant import JujuFactory
from tests.integration.helpers import deploy_control_plane


logger = logging.getLogger(__name__)


@fixture(scope="module")
def juju(request, juju_factory: JujuFactory):
    """Juju fixture providing a per-module temporary model.

    For test modules whose filename ends with ``_ssl``, teardown is skipped so the
    resulting model can be inspected or reused after the run.  All other modules
    fall through to the default per-module teardown provided by pytest-jubilant.
    """
    module_name = request.module.__name__
    is_ssl = module_name.endswith("_ssl")

    juju_instance = juju_factory.get_juju("")

    if request.config.getoption("--juju-switch"):
        assert juju_instance.model
        juju_instance.cli("switch", juju_instance.model, include_model=False)

    yield juju_instance

    if is_ssl:
        # Prevent pytest-jubilant's module-scoped juju_factory teardown from
        # destroying the SSL model so it remains available for inspection.
        juju_factory._models.pop(juju_instance.model, None)  # type: ignore[attr-defined]


@fixture(scope="module")
def deployment(juju):
    """Litmus deployment used for integration testing."""
    deploy_control_plane(juju, wait_for_active=True)
    yield juju
