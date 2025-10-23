# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest
from ops.testing import State, CharmEvents
from conftest import patch_cert_and_key_ctx
from litmus_auth import LitmusAuth


@pytest.mark.parametrize("tls", (False, True))
@pytest.mark.parametrize("leader", (False, True))
@pytest.mark.parametrize(
    "event",
    (
        CharmEvents.upgrade_charm(),
        CharmEvents.install(),
        CharmEvents.update_status(),
        CharmEvents.install(),
    ),
)
def test_ports_opened(ctx, event, authserver_container, leader, tls):
    # GIVEN a base deployment
    state = State(containers=[authserver_container])

    # WHEN any event fires
    with patch_cert_and_key_ctx(tls):
        state_out = ctx.run(ctx.on.update_status(), state=state)

    # THEN the workload_version is unset
    assert set(p.port for p in state_out.opened_ports) == (
        {LitmusAuth.https_port, LitmusAuth.grpc_tls_port}
        if tls
        else {LitmusAuth.http_port, LitmusAuth.grpc_port}
    )
