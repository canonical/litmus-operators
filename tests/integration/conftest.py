# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import logging

from pytest import fixture

from tests.integration.helpers import deploy_cluster


logger = logging.getLogger(__name__)


@fixture(scope="module")
def deployment(juju):
    """Litmus deployment used for integration testing."""
    deploy_cluster(juju, wait_for_active=True)
    yield juju



