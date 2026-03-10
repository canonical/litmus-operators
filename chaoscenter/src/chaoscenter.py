# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from pathlib import Path
from typing import Callable, Optional
from lightkube import Client
from lightkube.codecs import load_all_yaml
from ops import Secret

from litmus_client import LitmusClient
from user_manager import UserManager
from litmus_libs.interfaces.litmus_infrastructure import InfrastructureDatabagModel

logger = logging.getLogger(__name__)

LITMUS_CRD_MANIFEST_PATH = (
    Path(__file__).parent / "k8s_manifests" / "litmus_portal_crds.yaml"
)


class Chaoscenter:
    """Represents the Chaoscenter workload state and encapsulates all logic to operate it."""

    def __init__(
        self,
        endpoint: str,
        user_secret_id: Optional[str],
        get_secret: Callable[[str], Secret],
    ):
        self._k8s_client = Client()
        self._user_manager = UserManager(
            secret_id=user_secret_id,
            get_secret=get_secret,
            make_client=lambda username, password: LitmusClient(
                endpoint=endpoint, username=username, password=password
            ),
        )

    @property
    def user_secrets_valid(self) -> bool:
        """Returns True if the UserManager is ready to manage credentials, False otherwise."""
        return self._user_manager.user_secrets_valid

    def _apply_manifest(self, manifest: str):
        """Apply a k8s manifest to the cluster."""
        for obj in load_all_yaml(manifest):
            self._k8s_client.apply(
                obj, force=True, field_manager="litmus-chaoscenter-charm"
            )

    def reconcile(self):
        """Reconcile the state of the application, ensuring that all components are in their desired state."""
        self._user_manager.reconcile()

    def create_infrastructure(self, data: InfrastructureDatabagModel):
        """Create the infrastructure in Litmus if it doesn't exist, and apply the manifest to the cluster."""
        client = self._user_manager.get_charm_client()
        if not client:
            logger.warning(
                "Cannot authenticate charm client; cannot register infrastructure"
            )
            return
        project_id = client.default_project_id
        if not project_id:
            logger.warning(
                "Project ID is not available; cannot register infrastructure"
            )
            return
        name = data.infrastructure_name
        model_name = data.model_name

        existing_infra = client.get_infrastructure(name, model_name, project_id)
        if existing_infra and existing_infra.active:
            logger.info(
                f"Infrastructure {name} already exists and is active; skipping creation"
            )
            return

        if not existing_infra:
            infra_manifest = client.register_infrastructure(
                name, model_name, project_id
            )
        else:
            infra_manifest = client.get_infrastructure_manifest(
                existing_infra.id,
                project_id,
            )

        if infra_manifest:
            if not LITMUS_CRD_MANIFEST_PATH.exists():
                logger.warning(
                    f"Litmus CRD manifest not found at {LITMUS_CRD_MANIFEST_PATH}; skipping applying CRDs"
                )
            else:
                self._apply_manifest(LITMUS_CRD_MANIFEST_PATH.read_text())
            self._apply_manifest(infra_manifest)

    def delete_infrastructure(self, data: InfrastructureDatabagModel):
        """Delete the infrastructure from Litmus."""
        client = self._user_manager.get_charm_client()
        if not client:
            logger.warning(
                "Cannot authenticate charm client; cannot delete infrastructure"
            )
            return
        project_id = client.default_project_id
        if not project_id:
            logger.warning("Project ID is not available; cannot delete infrastructure")
            return
        name = data.infrastructure_name
        model_name = data.model_name

        existing_infra = client.get_infrastructure(name, model_name, project_id)
        if not existing_infra:
            logger.info(f"Infrastructure {name} doesn't exist; skipping deletion")
            return

        # TODO: investigate if we need to delete existing experiments in the infra before deleting the infra itself
        client.delete_infrastructure(existing_infra.id, project_id)
