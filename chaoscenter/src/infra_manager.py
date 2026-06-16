# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
"""This module contains the InfraManager class, which is responsible for managing the infrastructure in Chaoscenter."""

import logging
from pathlib import Path

from lightkube import Client, ApiError
from lightkube.codecs import load_all_yaml

from environment_manager import DEFAULT_ENVIRONMENT
from litmus_client import LitmusClient
from litmus_libs.interfaces.litmus_infrastructure import InfrastructureDatabagModel
from lightkube.generic_resource import create_namespaced_resource

logger = logging.getLogger(__name__)

# Define the Litmus Custom Resources
ChaosExperiment = create_namespaced_resource(
    group="litmuschaos.io",
    version="v1alpha1",
    kind="ChaosExperiment",
    plural="chaosexperiments",
)
ChaosEngine = create_namespaced_resource(
    group="litmuschaos.io",
    version="v1alpha1",
    kind="ChaosEngine",
    plural="chaosengines",
)
ChaosResult = create_namespaced_resource(
    group="litmuschaos.io",
    version="v1alpha1",
    kind="ChaosResult",
    plural="chaosresults",
)

LITMUS_CRD_MANIFEST_PATH = (
    Path(__file__).parent / "k8s_manifests" / "litmus_portal_crds.yaml"
)


class InfraManager:
    """Manages the Chaos Infrastructures in Chaoscenter."""

    def __init__(self, infrastructures: list[InfrastructureDatabagModel]):
        """Initialize InfraManager."""

        self._infrastructures = infrastructures
        self._k8s_client = Client()

    def reconcile(self, litmus_client: LitmusClient) -> None:
        """Reconcile the infrastructure with the desired state (relation data)."""
        project_id = litmus_client.get_default_project_id()

        actual_infra = {
            (infra.name, infra.namespace): infra
            for infra in litmus_client.list_infrastructures(
                project_id, DEFAULT_ENVIRONMENT
            )
        }
        desired_infra = {
            (infra.infrastructure_name, infra.model_name): infra
            for infra in self._infrastructures
        }

        infras_to_create = set(desired_infra) - set(actual_infra)
        infras_to_delete = set(actual_infra) - set(desired_infra)
        infras_existing = set(actual_infra) & set(desired_infra)
        infras_inactive = {k for k in infras_existing if not actual_infra[k].active}

        for infra_key in infras_to_create:
            self._create_infra(desired_infra[infra_key], project_id, litmus_client)

        for infra_key in infras_inactive:
            self._activate_infra(actual_infra[infra_key].id, project_id, litmus_client)

        for infra_key in infras_to_delete:
            self._delete_infra(
                actual_infra[infra_key].id,
                actual_infra[infra_key].namespace,
                project_id,
                litmus_client,
            )

    def _create_infra(
        self, infra: InfrastructureDatabagModel, project_id: str, client: LitmusClient
    ) -> None:
        infra_id = client.register_infrastructure(
            infra.infrastructure_name, infra.model_name, project_id, DEFAULT_ENVIRONMENT
        )
        self._activate_infra(infra_id, project_id, client)

    def _activate_infra(
        self, infra_id: str, project_id: str, client: LitmusClient
    ) -> None:
        manifest = client.get_infrastructure_manifest(infra_id, project_id)
        if manifest:
            self._apply_infra_manifest(manifest)

    def _apply_infra_manifest(self, manifest: str) -> None:
        if not LITMUS_CRD_MANIFEST_PATH.exists():
            logger.warning(
                f"Litmus CRD manifest not found at {LITMUS_CRD_MANIFEST_PATH}; skipping applying CRDs"
            )
        else:
            self._apply_manifest(LITMUS_CRD_MANIFEST_PATH.read_text())
        self._apply_manifest(manifest)

    def _delete_infra(
        self,
        infra_id: str,
        infra_namespace: str,
        project_id: str,
        client: LitmusClient,
    ) -> None:

        # 1. delete the execution plane components
        manifest = client.get_infrastructure_manifest(infra_id, project_id)
        if manifest:
            self._delete_manifest(manifest)

        # 2. delete chaos K8s resources in the infra namespace
        self._delete_chaos_experiments_from_k8s(namespace=infra_namespace)

        # 3. delete chaos experiments from the database
        self._delete_chaos_experiments_from_db(infra_id, project_id, client)

        # 4. delete the infrastructure from Chaoscenter
        client.delete_infrastructure(infra_id, project_id)

    def _apply_manifest(self, manifest: str) -> None:
        """Apply a k8s manifest to the cluster."""
        for obj in load_all_yaml(manifest):
            self._k8s_client.apply(
                obj, force=True, field_manager="litmus-chaoscenter-charm"
            )

    def _delete_manifest(self, manifest: str) -> None:
        """Delete a k8s manifest from the cluster."""
        for obj in load_all_yaml(manifest):
            if not obj.metadata or not obj.metadata.name:
                logger.warning(f"Skipping object with missing metadata or name: {obj}")
                continue
            resource = type(obj)
            name = obj.metadata.name
            namespace = obj.metadata.namespace
            try:
                self._k8s_client.delete(resource, name=name, namespace=namespace)  # type: ignore[arg-type]
            except ApiError:
                logger.warning(f"Failed to delete non-existing object {name}")

    def _delete_chaos_experiments_from_k8s(self, namespace):
        """Deletes all ChaosExperiments, ChaosEngines, and ChaosResults in a namespace."""
        for resource in [ChaosExperiment, ChaosEngine, ChaosResult]:
            try:
                self._k8s_client.deletecollection(resource, namespace=namespace)
            except ApiError:
                logger.warning(
                    f"Failed to delete chaos resources in namespace {namespace}"
                )

    def _delete_chaos_experiments_from_db(
        self, infra_id: str, project_id: str, client: LitmusClient
    ):
        """Deletes all chaos experiments in the database associated with an infrastructure."""
        existing_experiments = [
            experiment
            for experiment in client.list_experiments(project_id)
            if experiment.infra_id == infra_id
        ]
        for experiment in existing_experiments:
            client.delete_experiment(project_id=project_id, experiment_id=experiment.id)
