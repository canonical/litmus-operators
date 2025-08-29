# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
from litmus_libs.models import DatabaseConfig


def test_database_config_ignores_extra_args():
    # roundtrip test
    base = {"uris": "foo", "username": "bar", "password": "baz"}
    extras = {"somethingelse": "qux", "somethingyetelse": "quz"}
    assert DatabaseConfig(**base, **extras).model_dump() == base
