import json
import pytest
import ops
from ops.testing import Relation, State


@pytest.mark.parametrize("is_leader", (True, False))
def test_publish_infrastructure_data(ctx, is_leader):
    # GIVEN a charm
    infra_rel = Relation(endpoint="litmus-infrastructure")

    # WHEN the relation-joined event fires
    state_out = ctx.run(
        infra_rel.joined_event,
        state=State(
            relations={infra_rel},
            leader=is_leader,
            model=ops.testing.Model(name="test-model"),
        ),
    )

    databag = state_out.get_relation(infra_rel.id).local_app_data
    if is_leader:
        # THEN the application databag has the expected metadata
        assert "infrastructure_name" in databag
        assert "model_name" in databag
        assert json.loads(databag["model_name"]) == "test-model"
        assert json.loads(databag["infrastructure_name"]) == "test-model"
    else:
        # THEN the application databag should be empty because only the leader publishes data
        assert len(databag) == 0
