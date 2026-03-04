# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import json

import pytest
from ops import CharmBase
from ops.testing import Context, Relation, State

from litmus_libs.interfaces.litmus_infrastructure import (
    InfrastructureDatabagModel,
    LitmusInfrastructureProvider,
    LitmusInfrastructureRequirer,
)


class LitmusInfraCharm(CharmBase):
    """Mock charm to test the litmus-infrastructure interface."""

    META = {
        "name": "litmus-infra-tester",
        "provides": {"infra-provider": {"interface": "litmus_infrastructure"}},
        "requires": {"infra-requirer": {"interface": "litmus_infrastructure"}},
    }

    # Static storage for test assertions
    _PUBLISH_DATA: InfrastructureDatabagModel = None
    _RECEIVED_DATA: list[InfrastructureDatabagModel] = []

    def __init__(self, *args):
        super().__init__(*args)
        self.provider = LitmusInfrastructureProvider(
            self.model.relations["infra-provider"],
            self.app,
            self.unit,
        )
        self.requirer = LitmusInfrastructureRequirer(
            self.model.relations["infra-requirer"], self.app
        )

        self.framework.observe(self.on.update_status, self._on_update_status)

    def _on_update_status(self, _):
        if self._PUBLISH_DATA:
            self.provider.publish_data(self._PUBLISH_DATA)

        LitmusInfraCharm._RECEIVED_DATA = self.requirer.get_data()


@pytest.fixture(scope="function")
def ctx():
    yield Context(LitmusInfraCharm, meta=LitmusInfraCharm.META)
    LitmusInfraCharm._PUBLISH_DATA = None
    LitmusInfraCharm._RECEIVED_DATA = []


@pytest.fixture
def mock_metadata():
    return InfrastructureDatabagModel(
        infrastructure_name="test-cluster-123", model_name="production"
    )


def test_provider_publishes_metadata(ctx, mock_metadata):
    # GIVEN a charm with two relations
    rel1 = Relation(endpoint="infra-provider", id=1)
    rel2 = Relation(endpoint="infra-provider", id=2)

    LitmusInfraCharm._PUBLISH_DATA = mock_metadata

    # WHEN the provider publishes metadata
    state_out = ctx.run(
        ctx.on.update_status(),
        state=State(
            relations={rel1, rel2},
            leader=True,
        ),
    )

    # THEN both relations receive the data
    for rel_id in (1, 2):
        databag = state_out.get_relation(rel_id).local_app_data
        assert databag["infrastructure_name"] == json.dumps(mock_metadata.infrastructure_name)
        assert databag["model_name"] == json.dumps(mock_metadata.model_name)


def test_provider_fails_if_not_leader(ctx, mock_metadata):
    LitmusInfraCharm._PUBLISH_DATA = mock_metadata

    # GIVEN a charm where the unit is not the leader
    # WHEN the provider tries to publish metadata
    # THEN it raises an error
    with pytest.raises(RuntimeError):
        ctx.run(
            ctx.on.update_status(),
            state=State(
                relations={Relation(endpoint="infra-provider", id=1)},
                leader=False,
            ),
        )


def test_requirer_collects_multiple_providers(ctx):
    # GIVEN a requirer related to two different providers

    databag1 = {
        "infrastructure_name": json.dumps("cluster-a"),
        "model_name": json.dumps("model-a"),
    }
    databag2 = {
        "infrastructure_name": json.dumps("cluster-b"),
        "model_name": json.dumps("model-b"),
    }

    # WHEN the requirer charm runs
    ctx.run(
        ctx.on.update_status(),
        state=State(
            relations={
                Relation(endpoint="infra-requirer", id=1, remote_app_data=databag1),
                Relation(endpoint="infra-requirer", id=2, remote_app_data=databag2),
            },
        ),
    )

    # THEN the requirer correctly parses both metadata objects
    received = LitmusInfraCharm._RECEIVED_DATA
    assert len(received) == 2
    assert received[0].infrastructure_name == "cluster-a"
    assert received[1].infrastructure_name == "cluster-b"
    assert received[0].model_name == "model-a"
    assert received[1].model_name == "model-b"


def test_requirer_skips_uninitialized_provider(ctx):
    # GIVEN a relation exists but the remote app hasn't set any data yet
    ctx.run(
        ctx.on.update_status(),
        state=State(
            relations={Relation(endpoint="infra-requirer", id=1, remote_app_data={})},
        ),
    )

    # THEN the requirer returns an empty list
    received = LitmusInfraCharm._RECEIVED_DATA
    assert len(received) == 0


def test_requirer_fails_on_schema_type_mismatch(ctx):
    # GIVEN a provider sends data that doesn't match the expected schema (e.g. a list instead of a string)
    type_mismatch_databag = {"infrastructure_name": json.dumps(["list", "not", "string"])}

    # WHEN the requirer processes this relation
    ctx.run(
        ctx.on.update_status(),
        state=State(
            relations={
                Relation(endpoint="infra-requirer", id=1, remote_app_data=type_mismatch_databag)
            },
        ),
    )
    # THEN the requirer logs an error and returns an empty list
    assert len(LitmusInfraCharm._RECEIVED_DATA) == 0


def test_requirer_forward_compatibility(ctx):
    # GIVEN a provider sends the current fields PLUS a future "v2" field
    future_databag = {
        "infrastructure_name": json.dumps("cluster-1"),
        "model_name": json.dumps("prod"),
        "future_field_id": json.dumps("v2-xyz-789"),  # New field not in v1
    }

    # WHEN the requirer processes this relation
    ctx.run(
        ctx.on.update_status(),
        state=State(
            relations={Relation(endpoint="infra-requirer", id=1, remote_app_data=future_databag)},
        ),
    )

    # THEN the requirer ignores the unknown field but successfully parses the known ones
    received = LitmusInfraCharm._RECEIVED_DATA
    assert len(received) == 1
    assert received[0].infrastructure_name == "cluster-1"
    assert received[0].model_name == "prod"
    # Verify the object doesn't have the extra field (pydantic default behavior)
    assert not hasattr(received[0], "future_field_id")
