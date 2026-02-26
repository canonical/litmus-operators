# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import logging

from pytest import fixture
import os

from pytest_jubilant import pack

APP = "litmus-infrastructure"

logger = logging.getLogger(__name__)


@fixture(scope="session")
def charm():
    """Litmus infrastructure charm used for integration testing.

    Build once per session and reuse it in all integration tests to save some minutes/hours.
    You can also set `CHARM_PATH` env variable to use an already existing built charm.
    """
    if charm := os.getenv("CHARM_PATH"):
        return charm

    logger.info("packing...")
    return pack()
