# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
import os
import subprocess
from pathlib import Path

import yaml
from pytest_jubilant import pack

METADATA = yaml.safe_load(Path("./charmcraft.yaml").read_text())
CHAOSCENTER_APP = "litmus-chaoscenter"
CHAOSCENTER_RESOURCES = {
    image_name: image_meta["upstream-source"]
    for image_name, image_meta in METADATA["resources"].items()
}


logger = logging.getLogger(__name__)


def get_charm():
    if charm := os.getenv("CHARM_PATH"):
        return charm

    # Intermittent issue where charmcraft fails to build the charm for an unknown reason.
    # Retry building the charm
    for _ in range(3):
        logger.info("packing...")
        try:
            pth = pack()
        except subprocess.CalledProcessError:
            logger.warning("Failed to build chaoscenter charm. Trying again!")
            continue
        os.environ["CHARM_PATH"] = str(pth)
        return pth
    raise subprocess.CalledProcessError
