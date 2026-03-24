# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
import os
import secrets
from pathlib import Path

from pytest import fixture
from pytest_jubilant.main import TempModelFactory
from tests.integration.helpers import deploy_control_plane


logger = logging.getLogger(__name__)


@fixture(scope="module")
def juju(request, temp_model_factory):
    """Juju fixture providing a separate model for SSL tests with teardown disabled.

    Test modules whose filename ends with '_ssl' get their own model via a dedicated
    TempModelFactory.  The model is **not** torn down after the test session so it can
    be inspected or reused.  All other modules fall through to the default
    ``temp_model_factory`` provided by pytest-jubilant.
    """
    module_name = request.module.__name__
    is_ssl = module_name.endswith("_ssl")

    if is_ssl:
        user_model = request.config.getoption("--model")
        if user_model:
            prefix = f"{user_model}-ssl"
            randbits = None
        else:
            prefix = module_name.rpartition(".")[-1].replace("_", "-")
            randbits = (
                "testing"
                if os.getenv("PYTESTING_PYTEST_JUBILANT")
                else secrets.token_hex(4)
            )

        ssl_factory = TempModelFactory(
            prefix=prefix,
            randbits=randbits,
            check_models_unique=not user_model,
        )
        juju_instance = ssl_factory.get_juju("")

        if request.config.getoption("--switch"):
            juju_instance.cli("switch", juju_instance.model, include_model=False)

        yield juju_instance

        # Dump logs but explicitly skip teardown for SSL models
        if dump_logs := request.config.getoption("--dump-logs"):
            ssl_factory.dump_all_logs(Path(dump_logs))
    else:
        juju_instance = temp_model_factory.get_juju("")
        if request.config.getoption("--switch"):
            juju_instance.cli("switch", juju_instance.model, include_model=False)
        yield juju_instance


@fixture(scope="module")
def deployment(juju):
    """Litmus deployment used for integration testing."""
    deploy_control_plane(juju, wait_for_active=True)
    yield juju
