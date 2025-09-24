# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
import pathlib
import subprocess
import jubilant
import pytest

from pytest_bdd import given, when, then

logger = logging.getLogger(__name__)

TESTS_DIR = pathlib.Path(__file__).parent.resolve()


@pytest.fixture
def juju():
    with jubilant.temp_model() as tm:
        yield tm


@given("a juju model")
@when("you run terraform apply using the provided module")
def test_terraform_apply(juju):
    subprocess.check_call(["terraform", f"-chdir={TESTS_DIR}", "init"])
    subprocess.check_call(
        f"terraform -chdir={TESTS_DIR} apply -var \"model={juju.model}\" -auto-approve",
        shell=True,
    )


@then("litmus charms are deployed and active")
def test_active(juju):
    juju.wait(jubilant.all_active, timeout=60 * 10)
