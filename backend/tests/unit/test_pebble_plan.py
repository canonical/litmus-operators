# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
from ops.testing import State
from dataclasses import replace

import pytest
from conftest import (
    db_remote_databag,
    auth_remote_databag,
    http_api_remote_databag,
    patch_cert_and_key_ctx,
)
from litmus_backend import LitmusBackend


def test_pebble_plan_minimal(ctx, backend_container):
    expected_env_vars = {
        "REST_PORT",
        "GRPC_PORT",
        "INFRA_DEPLOYMENTS",
        "DEFAULT_HUB_BRANCH_NAME",
        "ALLOWED_ORIGINS",
        "CONTAINER_RUNTIME_EXECUTOR",
        "WORKFLOW_HELPER_IMAGE_VERSION",
        "INFRA_COMPATIBLE_VERSIONS",
        "VERSION",
        "SUBSCRIBER_IMAGE",
        "EVENT_TRACKER_IMAGE",
        "ARGO_WORKFLOW_CONTROLLER_IMAGE",
        "ARGO_WORKFLOW_EXECUTOR_IMAGE",
        "LITMUS_CHAOS_OPERATOR_IMAGE",
        "LITMUS_CHAOS_RUNNER_IMAGE",
        "LITMUS_CHAOS_EXPORTER_IMAGE",
    }

    # GIVEN a running container with no relations
    state = State(containers=[backend_container], relations=[])

    # WHEN a workload pebble ready event is fired
    state_out = ctx.run(ctx.on.pebble_ready(backend_container), state=state)

    # THEN litmus backend server pebble plan is generated with the right env vars
    backend_container_out = state_out.get_container(backend_container.name)
    actual_env_vars = backend_container_out.plan.to_dict()["services"]["backend"][
        "environment"
    ]
    assert actual_env_vars.keys() == expected_env_vars

    # AND the pebble service is NOT running
    assert not backend_container_out.services.get("backend").is_running()


def test_pebble_plan_with_database_relation(ctx, backend_container, database_relation):
    expected_env_vars = {
        "DB_USER",
        "DB_PASSWORD",
        "DB_SERVER",
    }
    # GIVEN a running container with a database relation
    database_relation = replace(
        database_relation,
        remote_app_data=db_remote_databag(),
    )
    state = State(containers=[backend_container], relations=[database_relation])

    # WHEN a relation changed event is fired
    state_out = ctx.run(ctx.on.relation_changed(database_relation), state=state)

    # THEN litmus backend server pebble plan is generated with extra db env vars
    backend_container_out = state_out.get_container(backend_container.name)
    actual_env_vars = backend_container_out.plan.to_dict()["services"]["backend"][
        "environment"
    ]
    assert expected_env_vars.issubset(actual_env_vars.keys())

    # AND the pebble service is running
    assert backend_container_out.services.get("backend").is_running()


def test_pebble_plan_with_auth_relation(ctx, backend_container, auth_relation):
    expected_env_vars = {
        "LITMUS_AUTH_GRPC_ENDPOINT",
        "LITMUS_AUTH_GRPC_PORT",
    }
    # GIVEN a running container with an auth relation
    auth_relation = replace(
        auth_relation,
        remote_app_data=auth_remote_databag(),
    )
    state = State(containers=[backend_container], relations=[auth_relation])

    # WHEN a relation changed event is fired
    state_out = ctx.run(ctx.on.relation_changed(auth_relation), state=state)

    # THEN litmus backend server pebble plan is generated with extra db env vars
    backend_container_out = state_out.get_container(backend_container.name)
    actual_env_vars = backend_container_out.plan.to_dict()["services"]["backend"][
        "environment"
    ]
    assert expected_env_vars.issubset(actual_env_vars.keys())

    # AND the pebble service is NOT running
    assert not backend_container_out.services.get("backend").is_running()


def test_pebble_plan_with_backend_http_api_relation(
    ctx, backend_container, http_api_relation
):
    expected_env_vars = {
        "CHAOS_CENTER_UI_ENDPOINT",
    }
    # GIVEN a running container with a backend-http-api relation
    http_api_relation = replace(
        http_api_relation,
        remote_app_data=http_api_remote_databag(),
    )
    state = State(containers=[backend_container], relations=[http_api_relation])

    # WHEN a relation changed event is fired
    state_out = ctx.run(ctx.on.relation_changed(http_api_relation), state=state)

    # THEN litmus backend server pebble plan is generated with extra db env vars
    backend_container_out = state_out.get_container(backend_container.name)
    actual_env_vars = backend_container_out.plan.to_dict()["services"]["backend"][
        "environment"
    ]
    assert expected_env_vars.issubset(actual_env_vars.keys())

    # AND the pebble service is NOT running
    assert not backend_container_out.services.get("backend").is_running()


def test_pebble_plan_with_tls_certificates_relation(
    ctx, backend_container, tls_certificates_relation, patch_cert_and_key
):
    expected_env_vars = {
        "ENABLE_INTERNAL_TLS",
        "REST_PORT",
        "GRPC_PORT",
        "TLS_CERT_PATH",
        "TLS_KEY_PATH",
        "CA_CERT_TLS_PATH",
    }

    # GIVEN a running container with a tls-certificates relation
    state = State(containers=[backend_container], relations=[tls_certificates_relation])

    # WHEN a relation changed event is fired
    state_out = ctx.run(ctx.on.relation_changed(tls_certificates_relation), state=state)

    # THEN litmus backend server pebble plan is generated with extra TLS env vars
    backend_container_out = state_out.get_container(backend_container.name)
    actual_env_vars = backend_container_out.plan.to_dict()["services"]["backend"][
        "environment"
    ]
    assert expected_env_vars.issubset(actual_env_vars.keys())

    # AND the pebble service is NOT running
    assert not backend_container_out.services.get("backend").is_running()


def test_pebble_service_running(
    ctx, backend_container, auth_relation, database_relation
):
    # GIVEN a running container with an auth and a database relation
    auth_relation = replace(
        auth_relation,
        remote_app_data=auth_remote_databag(),
    )
    database_relation = replace(
        database_relation,
        remote_app_data=db_remote_databag(),
    )
    state = State(
        containers=[backend_container], relations=[auth_relation, database_relation]
    )

    # WHEN a relation changed event is fired
    state_out = ctx.run(ctx.on.relation_changed(auth_relation), state=state)

    # THEN litmus backend server pebble service is running
    backend_container_out = state_out.get_container(backend_container.name)
    assert backend_container_out.services.get("backend").is_running()


@pytest.mark.parametrize("workload_version_set", (True, False))
def test_workload_version_in_pebble_env_vars(
    ctx, backend_container, patch_workload_version, workload_version_set
):
    patch_workload_version.return_value = "1.0" if workload_version_set else None
    expected_env_vars = {
        "WORKFLOW_HELPER_IMAGE_VERSION",
        "VERSION",
        "INFRA_COMPATIBLE_VERSIONS",
        "SUBSCRIBER_IMAGE",
        "EVENT_TRACKER_IMAGE",
        "LITMUS_CHAOS_OPERATOR_IMAGE",
        "LITMUS_CHAOS_RUNNER_IMAGE",
        "LITMUS_CHAOS_EXPORTER_IMAGE",
    }

    # GIVEN a running container
    state = State(containers=[backend_container])

    # WHEN any event is fired
    state_out = ctx.run(ctx.on.update_status(), state=state)

    backend_container_out = state_out.get_container(backend_container.name)
    actual_env_vars = backend_container_out.plan.to_dict()["services"]["backend"][
        "environment"
    ]
    # THEN litmus backend server pebble plan env vars has the workload version set (if it's non empty)
    for key in expected_env_vars:
        if workload_version_set:
            assert "1.0" in actual_env_vars[key]
        else:
            assert "1.0" not in actual_env_vars[key]


@pytest.mark.parametrize("tls", (False, True))
def test_pebble_checks_plan(
    ctx, backend_container, auth_relation, database_relation, tls, unit_fqdn
):
    # GIVEN a running container with an auth and a database relation
    auth_relation = replace(
        auth_relation,
        remote_app_data=auth_remote_databag(),
    )
    database_relation = replace(
        database_relation,
        remote_app_data=db_remote_databag(),
    )
    state = State(
        containers=[backend_container], relations=[auth_relation, database_relation]
    )
    with patch_cert_and_key_ctx(tls):
        # WHEN a workload pebble ready event is fired
        state_out = ctx.run(ctx.on.relation_changed(auth_relation), state=state)

    # THEN litmus backend server pebble plan is generated with the correct pebble checks
    backend_container_out = state_out.get_container(backend_container.name)
    assert backend_container_out.plan.checks["backend-up"].tcp == {
        "port": 8081 if tls else 8080
    }


# ──────────────────────────────────────────────────────────────────────────────
# Manifest template patching tests
# ──────────────────────────────────────────────────────────────────────────────

_MANIFEST_WITH_ARGO33_ARTEFACTS = """\
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: workflow-controller-configmap
  namespace: #{INFRA_NAMESPACE}
data:
  containerRuntimeExecutor: #{ARGO_CONTAINER_RUNTIME_EXECUTOR}
  executor: |
    imagePullPolicy: IfNotPresent
  instanceID: #{INFRA_ID}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: workflow-controller
spec:
  template:
    spec:
      containers:
        - args:
            - --configmap
            - workflow-controller-configmap
            - --executor-image
            - charmedkubeflow/argoexec:3.4.17-ae093c9
            - --namespaced
            - --container-runtime-executor
            - emissary
          command:
            - workflow-controller
          image: charmedkubeflow/workflow-controller:3.4.17-627976f
"""

_MANIFEST_CLEAN = """\
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: workflow-controller-configmap
  namespace: #{INFRA_NAMESPACE}
data:
  executor: |
    imagePullPolicy: IfNotPresent
  instanceID: #{INFRA_ID}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: workflow-controller
spec:
  template:
    spec:
      containers:
        - args:
            - --configmap
            - workflow-controller-configmap
            - --executor-image
            - charmedkubeflow/argoexec:3.4.17-ae093c9
            - --namespaced
          command:
            - workflow-controller
          image: charmedkubeflow/workflow-controller:3.4.17-627976f
"""


def test_patch_argo_manifest_strips_configmap_key_and_cli_flag():
    # GIVEN a manifest template with both Argo 3.3 artefacts
    # WHEN the patching method is called
    result = LitmusBackend._patch_argo_manifest(_MANIFEST_WITH_ARGO33_ARTEFACTS)
    # THEN the containerRuntimeExecutor ConfigMap key is removed
    assert "containerRuntimeExecutor" not in result
    # AND the --container-runtime-executor CLI flag and its value are removed
    assert "--container-runtime-executor" not in result
    assert "- emissary\n" not in result
    # AND the rest of the ConfigMap and Deployment are preserved intact
    assert "executor: |" in result
    assert "instanceID:" in result
    assert "--executor-image" in result
    assert "workflow-controller-configmap" in result
    assert "--namespaced" in result


def test_patch_argo_manifest_is_idempotent():
    # GIVEN a manifest that already has the Argo 3.3 artefacts removed
    # WHEN the patching method is called again
    result = LitmusBackend._patch_argo_manifest(_MANIFEST_CLEAN)
    # THEN the content is unchanged
    assert result == _MANIFEST_CLEAN


# ──────────────────────────────────────────────────────────────────────────────
# Argo CRDs patching tests
# ──────────────────────────────────────────────────────────────────────────────

_ARGO_CRDS_WITHOUT_ARTIFACT_GC = """\
---
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: workflows.argoproj.io
spec:
  group: argoproj.io
  names:
    kind: Workflow
    plural: workflows
  scope: Namespaced
  versions:
  - name: v1alpha1
    served: true
    storage: true
"""

_ARGO_CRDS_WITH_ARTIFACT_GC = (
    _ARGO_CRDS_WITHOUT_ARTIFACT_GC.rstrip("\n")
    + "\n"
    + LitmusBackend._WORKFLOW_ARTIFACT_GC_TASK_CRD
)


def test_patch_argo_crds_adds_missing_crd(ctx, backend_container):
    import os
    import tempfile
    from ops.testing import Mount

    with tempfile.TemporaryDirectory() as tmpdir:
        cluster_dir = os.path.join(tmpdir, "cluster")
        os.makedirs(cluster_dir)
        crd_path = os.path.join(cluster_dir, "1a_argo_crds.yaml")
        with open(crd_path, "w") as f:
            f.write(_ARGO_CRDS_WITHOUT_ARTIFACT_GC)

        # GIVEN a container whose argo CRDs manifest does not have the artifact GC CRD
        backend_container.mounts["manifests"] = Mount(
            location="/manifests", source=tmpdir
        )
        state = State(containers=[backend_container])

        # WHEN a pebble ready event is fired
        ctx.run(ctx.on.pebble_ready(backend_container), state=state)

        # THEN the CRD is appended to the manifest
        with open(crd_path) as f:
            result = f.read()
        assert "workflowartifactgctasks.argoproj.io" in result
        assert "WorkflowArtifactGCTask" in result


def test_patch_argo_crds_is_idempotent(ctx, backend_container):
    import os
    import tempfile
    from ops.testing import Mount

    with tempfile.TemporaryDirectory() as tmpdir:
        cluster_dir = os.path.join(tmpdir, "cluster")
        os.makedirs(cluster_dir)
        crd_path = os.path.join(cluster_dir, "1a_argo_crds.yaml")
        with open(crd_path, "w") as f:
            f.write(_ARGO_CRDS_WITH_ARTIFACT_GC)

        # GIVEN a container whose argo CRDs manifest already has the artifact GC CRD
        backend_container.mounts["manifests"] = Mount(
            location="/manifests", source=tmpdir
        )
        state = State(containers=[backend_container])

        # WHEN a pebble ready event is fired
        ctx.run(ctx.on.pebble_ready(backend_container), state=state)

        # THEN the CRD appears exactly once
        with open(crd_path) as f:
            result = f.read()
        assert result.count("workflowartifactgctasks.argoproj.io") == 1
