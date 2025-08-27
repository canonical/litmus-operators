# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
from interface_tester import InterfaceTester


def test_litmus_auth_v0_interface(litmus_auth_tester: InterfaceTester):
    litmus_auth_tester.configure(
        interface_name="litmus_auth",
        interface_version=0,
    )
    litmus_auth_tester.run()
