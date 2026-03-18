# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import os
import pathlib
import subprocess
import jubilant
import pytest
import yaml

from pytest_bdd import given, when, then


THIS_DIRECTORY = pathlib.Path(__file__).parent.resolve()
CHARM_CHANNEL = "dev/edge"
ADMIN_PASSWORD = "Litmus123!"
CHARM_PASSWORD = "Charm123!"


@pytest.fixture(scope="module")
def juju():
    with jubilant.temp_model() as tm:
        yield tm


@given("a juju model")
@when("you run terraform apply using the provided module")
def test_terraform_apply(juju: jubilant.Juju):
    base_cmd = ["terraform", f"-chdir={THIS_DIRECTORY}"]

    # Initialize
    subprocess.run([*base_cmd, "init"], check=True)

    # Prepare Environment for Secrets (Hides them from the process list)
    tf_env = os.environ.copy()
    tf_env["TF_VAR_admin_password"] = ADMIN_PASSWORD
    tf_env["TF_VAR_charm_password"] = CHARM_PASSWORD
    apply_cmd = [
        *base_cmd,
        "apply",
        f"-var=channel={CHARM_CHANNEL}",
        f"-var=model_uuid={_get_juju_model_uuid(juju)}",
        "-auto-approve",
    ]
    subprocess.run(apply_cmd, env=tf_env, check=True)


@then("litmus charms are deployed and active")
def test_active(juju):
    juju.wait(
        lambda status: jubilant.all_active(
            status, "litmus-auth", "litmus-backend", "litmus-chaoscenter"
        ),
        timeout=60 * 10,
    )


def _get_juju_model_uuid(juju: jubilant.Juju) -> str:
    """This is a workaround for juju.show_model() not working."""
    model_details = yaml.safe_load(
        juju.cli("show-model", juju.model, include_model=False)
    )
    return model_details[juju.model]["model-uuid"]
