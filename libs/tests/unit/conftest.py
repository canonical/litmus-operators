# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest
from ops.testing import Relation


@pytest.fixture(scope="function")
def litmus_auth():
    return Relation("litmus-auth")
