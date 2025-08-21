# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import logging

from pytest import fixture
import os
from pathlib import Path

import yaml
from pytest_jubilant import pack

_METADATA = yaml.safe_load(Path("./charmcraft.yaml").read_text())
APP = "litmus-backend"
RESOURCES = {
    image_name: image_meta["upstream-source"]
    for image_name, image_meta in _METADATA["resources"].items()
}

logger = logging.getLogger(__name__)


@fixture(scope="session")
def charm():
    """Litmus backend server charm used for integration testing.

    Build once per session and reuse it in all integration tests to save some minutes/hours.
    You can also set `CHARM_PATH` env variable to use an already existing built charm.
    """
    if charm := os.getenv("CHARM_PATH"):
        return charm

    logger.info("packing...")
    return pack()
