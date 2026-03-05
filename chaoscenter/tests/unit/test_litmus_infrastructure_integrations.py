from pathlib import Path
from unittest.mock import MagicMock, patch
from ops.testing import State
import pytest
from types import SimpleNamespace
from litmus_client import ChaosInfrastructure

MOCK_PROJECT_ID = "default_project_id"


@pytest.fixture()
def patch_apply_manifests():
    with patch("charm.LitmusChaoscenterCharm._apply_manifest") as mock_apply:
        yield mock_apply


@pytest.fixture
def patch_crd_mainfests_path(tmp_path):
    mock_crd_file = Path(tmp_path / "sample_crd.yaml")
    mock_crd_file.write_text("apiVersion: v1\nkind: SampleCRD")
    with patch("charm.LITMUS_CRD_MANIFEST_PATH", mock_crd_file):
        yield mock_crd_file


@pytest.fixture
def mock_litmus_client():
    mock = MagicMock()
    mock.return_value.default_project_id = MOCK_PROJECT_ID
    return mock


@pytest.fixture
def mock_infra_data():
    infra = MagicMock()
    infra.return_value.get_data.return_value = SimpleNamespace(
        infrastructure_name="k8s-infra",
        model_name="prod-model",
    )
    return infra


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


def test_infrastructure_creation_on_relation_changed(
    ctx,
    litmus_infrastructure_relation,
    nginx_container,
    nginx_prometheus_exporter_container,
    mock_litmus_client,
    mock_infra_data,
    patch_crd_mainfests_path,
    patch_apply_manifests,
):
    """Verifies that the charm registers and applies infrastructure when it doesn't exist."""
    # GIVEN a leader charm with a relation providing infrastructure data
    state_in = State(
        leader=True,
        relations={litmus_infrastructure_relation},
        containers={nginx_container, nginx_prometheus_exporter_container},
    )

    # Setup Client mocks: Infra doesn't exist yet

    # WHEN the relation changed event is fired
    # We patch the internal client and relation interface
    with (
        patch("charm.LitmusClient", mock_litmus_client),
        patch("charm.LitmusInfrastructureRequirer", mock_infra_data),
    ):
        mock_litmus_client.return_value.get_infrastructure.return_value = None
        mock_litmus_client.return_value.register_infrastructure.return_value = (
            "kind: Deployment\nname: agent"
        )
        ctx.run(ctx.on.relation_changed(litmus_infrastructure_relation), state_in)

        # THEN the charm should register the infrastructure
        mock_litmus_client.return_value.register_infrastructure.assert_called_once_with(
            "k8s-infra", "prod-model", MOCK_PROJECT_ID
        )

        # AND the charm should apply both the CRDs and the newly generated manifest
        assert patch_apply_manifests.call_count == 2
        patch_apply_manifests.assert_any_call(patch_crd_mainfests_path.read_text())
        patch_apply_manifests.assert_any_call("kind: Deployment\nname: agent")


def test_infrastructure_skipped_if_already_active(
    ctx,
    litmus_infrastructure_relation,
    mock_litmus_client,
    patch_apply_manifests,
    mock_infra_data,
    nginx_container,
    nginx_prometheus_exporter_container,
):
    """Verifies idempotency: skip registration if infrastructure is already active."""
    state_in = State(
        leader=True,
        relations={litmus_infrastructure_relation},
        containers={nginx_container, nginx_prometheus_exporter_container},
    )

    # GIVEN the infrastructure already exists and is active
    mock_litmus_client.return_value.get_infrastructure.return_value = (
        ChaosInfrastructure(
            id="infra-123", name="k8s-infra", environment_id="test", active=True
        )
    )

    with (
        patch("charm.LitmusClient", mock_litmus_client),
        patch("charm.LitmusInfrastructureRequirer", mock_infra_data),
    ):
        ctx.run(ctx.on.relation_changed(litmus_infrastructure_relation), state_in)

        # THEN registration is skipped and nothing is applied
        mock_litmus_client.return_value.register_infrastructure.assert_not_called()
        patch_apply_manifests.assert_not_called()


def test_infrastructure_reapplied_if_inactive(
    ctx,
    litmus_infrastructure_relation,
    mock_litmus_client,
    patch_apply_manifests,
    nginx_container,
    nginx_prometheus_exporter_container,
    mock_infra_data,
):
    """Verifies that we re-fetch and apply the manifest if the infra is inactive."""
    state_in = State(
        leader=True,
        relations={litmus_infrastructure_relation},
        containers={nginx_container, nginx_prometheus_exporter_container},
    )

    # GIVEN infrastructure exists but is NOT active
    mock_litmus_client.return_value.get_infrastructure.return_value = (
        ChaosInfrastructure(
            id="infra-123", name="k8s-infra", environment_id="test", active=False
        )
    )
    mock_litmus_client.return_value.get_infrastructure_manifest.return_value = (
        "re-apply-this-yaml"
    )

    with (
        patch("charm.LitmusClient", mock_litmus_client),
        patch("charm.LitmusInfrastructureRequirer", mock_infra_data),
    ):
        ctx.run(ctx.on.relation_changed(litmus_infrastructure_relation), state_in)

        # THEN we fetch the manifest for the existing ID
        mock_litmus_client.return_value.get_infrastructure_manifest.assert_called_once_with(
            "infra-123", MOCK_PROJECT_ID
        )
        # AND apply it
        patch_apply_manifests.assert_any_call("re-apply-this-yaml")


def test_infrastructure_deleted_on_relation_departed(
    ctx,
    litmus_infrastructure_relation,
    mock_litmus_client,
    nginx_container,
    nginx_prometheus_exporter_container,
    mock_infra_data,
):
    """Verifies that infrastructure is deleted from the backend when the relation is departing."""
    state_in = State(
        leader=True,
        relations={litmus_infrastructure_relation},
        containers={nginx_container, nginx_prometheus_exporter_container},
    )

    # GIVEN infrastructure exists
    mock_litmus_client.return_value.get_infrastructure.return_value = (
        ChaosInfrastructure(
            id="infra-uuid", name="k8s-infra", environment_id="test", active=True
        )
    )

    with (
        patch("charm.LitmusClient", mock_litmus_client),
        patch("charm.LitmusInfrastructureRequirer", mock_infra_data),
    ):
        ctx.run(ctx.on.relation_departed(litmus_infrastructure_relation), state_in)

        # THEN the client should be called to delete the specific infrastructure
        mock_litmus_client.return_value.delete_infrastructure.assert_called_once_with(
            "infra-uuid", MOCK_PROJECT_ID
        )
