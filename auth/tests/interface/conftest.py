# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest
from interface_tester import InterfaceTester

from scenario.state import Container, State

from charm import LitmusAuthCharm


def authserver_container():
    return Container(
        name="authserver",
        can_connect=True,
    )


# Interface tests are centrally hosted at https://github.com/canonical/charm-relation-interfaces.
# this fixture is used by the test runner of charm-relation-interfaces to test litmus auth's compliance
# with the interface specifications.
# DO NOT MOVE OR RENAME THIS FIXTURE! If you need to, you'll need to open a PR on
# https://github.com/canonical/charm-relation-interfaces and change litmus_auth's test configuration
# to include the new identifier/location.
@pytest.fixture
def litmus_auth_tester(interface_tester: InterfaceTester):
    interface_tester.configure(
        charm_type=LitmusAuthCharm,
        state_template=State(
            leader=True,
            containers=[authserver_container()],
        ),
    )
    yield interface_tester
