# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
from .helpers import deploy_control_plane
from pytest import fixture


logger = logging.getLogger(__name__)


@fixture(scope="module")
def deployment(juju):
    """Litmus deployment used for integration testing."""
    deploy_control_plane(juju, wait_for_active=True)
    yield juju
