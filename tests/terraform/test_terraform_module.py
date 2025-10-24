# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import shlex
import pathlib
import subprocess
import jubilant
import pytest

from pytest_bdd import given, when, then


THIS_DIRECTORY = pathlib.Path(__file__).parent.resolve()
CHARM_CHANNEL = "2/edge"


@pytest.fixture(scope="module")
def juju():
    with jubilant.temp_model() as tm:
        yield tm


@given("a juju model")
@when("you run terraform apply using the provided module")
def test_terraform_apply(juju):
    subprocess.run(shlex.split(f"terraform -chdir={THIS_DIRECTORY} init"), check=True)
    subprocess.run(
        shlex.split(
            f'terraform -chdir={THIS_DIRECTORY} apply -var="channel={CHARM_CHANNEL}" '
            f'-var="model={juju.model}" -auto-approve'
        ),
        check=True,
    )


@then("litmus charms are deployed and active")
def test_active(juju):
    juju.wait(
        lambda status: jubilant.all_active(
            status, "litmus-auth", "litmus-backend", "litmus-chaoscenter"
        ),
        timeout=60 * 10,
    )
