from ops.testing import State


def test_get_relation_data(
    ctx,
    litmus_infrastructure_relation,
    nginx_container,
    nginx_prometheus_exporter_container,
):
    """
    Verifies that the charm correctly receives the data from the infrastructure rel provider.
    """
    # GIVEN a litmus infrastructure relation with remote app data containing the infrastructure name and model name
    state_in = State(
        leader=True,
        relations={litmus_infrastructure_relation},
        containers={nginx_container, nginx_prometheus_exporter_container},
    )

    # WHEN any event is fired
    with ctx(ctx.on.update_status(), state_in) as mgr:
        charm = mgr.charm
        # THEN the charm should be able to acquire the data from the relation and parse it correctly
        data = charm._litmus_infra.get_data(litmus_infrastructure_relation.id)
        assert data.infrastructure_name == "name"
        assert data.model_name == "model"
