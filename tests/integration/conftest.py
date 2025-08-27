# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
import os
from pathlib import Path
from typing import Literal

from pytest import fixture
from pytest_jubilant import pack, get_resources


logger = logging.getLogger(__name__)


def _charm_and_channel_and_resources(
    role: Literal["auth", "backend"], charm_path_key: str, charm_channel_key: str
):
    """Litmus charms used for integration testing.

    Build once per session and reuse it in all integration tests.
    """
    # deploy charm from charmhub
    if channel_from_env := os.getenv(charm_channel_key):
        charm = f"litmus-{role}-k8s"
        logger.info(f"Using published {charm} charm from {channel_from_env}")
        return charm, channel_from_env, None
    # else deploy from a charm packed locally
    elif path_from_env := os.getenv(charm_path_key):
        charm_path = Path(path_from_env).absolute()
        logger.info("Using local {role} charm: %s", charm_path)
        return (
            charm_path,
            None,
            get_resources(charm_path.parent),
        )
    # else pack the charm
    return pack(Path() / role), None, get_resources(Path().parent / role)


@fixture(scope="session")
def auth_charm_metadata():
    """Metadata for the Litmus auth charm, including the charm_url, channel, and resources."""
    return _charm_and_channel_and_resources(
        "auth", "AUTH_CHARM_PATH", "AUTH_CHARM_CHANNEL"
    )


@fixture(scope="session")
def backend_charm_metadata():
    """Metadata for the Litmus backend charm, including the charm_url, channel, and resources."""
    return _charm_and_channel_and_resources(
        "backend", "BACKEND_CHARM_PATH", "BACKEND_CHARM_CHANNEL"
    )
