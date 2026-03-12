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


@pytest.fixture(scope="function")
def ctx():
    return Context(LitmusInfraCharm, meta=LitmusInfraCharm.META)


@pytest.fixture
def mock_metadata():
    return InfrastructureDatabagModel(
        infrastructure_name="test-cluster-123", model_name="production"
    )


def test_provider_publishes_metadata(ctx, mock_metadata):
    # GIVEN a charm with two relations
    rel1, rel2 = (
        Relation(endpoint="infra-provider", id=1),
        Relation(endpoint="infra-provider", id=2),
    )
    state = State(relations={rel1, rel2}, leader=True)

    # WHEN the provider publishes metadata
    with ctx(ctx.on.update_status(), state=state) as mgr:
        mgr.charm.provider.publish_data(mock_metadata)
        state_out = mgr.run()

    # THEN both relations receive the data
    for rel_id in (1, 2):
        databag = state_out.get_relation(rel_id).local_app_data
        assert json.loads(databag["infrastructure_name"]) == "test-cluster-123"
        assert json.loads(databag["model_name"]) == "production"


def test_provider_fails_if_not_leader(ctx, mock_metadata):
    # GIVEN a charm that is not the leader
    state = State(relations={Relation(endpoint="infra-provider", id=1)}, leader=False)

    # WHEN/THEN attempting to publish raises RuntimeError
    with ctx(ctx.on.update_status(), state=state) as mgr:
        with pytest.raises(RuntimeError):
            mgr.charm.provider.publish_data(mock_metadata)


def test_requirer_get_all_data(ctx):
    # GIVEN a requirer related to two different providers

    databag1 = {
        "infrastructure_name": json.dumps("cluster-a"),
        "model_name": json.dumps("model-a"),
    }
    databag2 = {
        "infrastructure_name": json.dumps("cluster-b"),
        "model_name": json.dumps("model-b"),
    }

    state = State(
        relations={
            Relation(endpoint="infra-requirer", id=1, remote_app_data=databag1),
            Relation(endpoint="infra-requirer", id=2, remote_app_data=databag2),
        },
    )
    # WHEN the requirer charm runs
    with ctx(ctx.on.update_status(), state=state) as mgr:
        req = mgr.charm.requirer
        # THEN get_all_data() retuns data from both providers
        received = req.get_all_data()
        assert len(received) == 2
        assert received[0].infrastructure_name == "cluster-a"
        assert received[1].infrastructure_name == "cluster-b"
        assert received[0].model_name == "model-a"
        assert received[1].model_name == "model-b"


def test_requirer_skips_uninitialized_provider(ctx):
    # GIVEN a relation exists but the remote app hasn't set any data yet
    state = State(
        relations={Relation(endpoint="infra-requirer", id=1, remote_app_data={})},
    )

    # WHEN the requirer tries to get relation data
    with ctx(ctx.on.update_status(), state=state) as mgr:
        # THEN the data is empty
        assert mgr.charm.requirer.get_all_data() == []


def test_requirer_handles_malformed_data(ctx):
    # GIVEN a provider sends data that doesn't match the expected schema (e.g. a list instead of a string)
    type_mismatch_databag = {"infrastructure_name": json.dumps(["list", "not", "string"])}

    # WHEN the requirer processes this relation
    state = State(
        relations={
            Relation(endpoint="infra-requirer", id=1, remote_app_data=type_mismatch_databag)
        }
    )
    with ctx(ctx.on.update_status(), state=state) as mgr:
        # THEN the API handle the error gracefully by returning None
        assert mgr.charm.requirer.get_all_data() == []


def test_requirer_forward_compatibility(ctx):
    # GIVEN data with extra unknown fields
    future_databag = {
        "infrastructure_name": json.dumps("cluster-1"),
        "model_name": json.dumps("prod"),
        "extra_v2_field": json.dumps("ignored"),
    }
    state = State(
        relations={Relation(endpoint="infra-requirer", id=1, remote_app_data=future_databag)}
    )

    # WHEN the requirer processes this relation
    with ctx(ctx.on.update_status(), state=state) as mgr:
        received = mgr.charm.requirer.get_all_data()

        # THEN the requirer ignores the unknown field but successfully parses the known ones
        assert received[0].infrastructure_name == "cluster-1"
        assert received[0].model_name == "prod"
        # Verify the object doesn't have the extra field (pydantic default behavior)
        assert not hasattr(received[0], "extra_v2_field")
