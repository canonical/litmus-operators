#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Control Litmus Backend server running in a container under Pebble. Provides a LitmusBackend class."""

import json
import logging

from ops import Container
from ops.pebble import Layer, CheckDict, ConnectionError
from typing import Optional, Callable
from litmus_libs import DatabaseConfig, TLSConfigData, get_litmus_version
from litmus_libs.interfaces.litmus_auth import Endpoint

logger = logging.getLogger(__name__)


class LitmusBackend:
    """Litmus Backend server workload."""

    container_name = "backend"
    layer_name = "backend"
    service_name = "backend"
    liveness_check_name = "backend-up"
    http_port = 8080
    https_port = 8081
    grpc_port = 8000
    grpc_tls_port = 8001
    all_pebble_checks = [liveness_check_name]

    def __init__(
        self,
        container: Container,
        tls_cert_path: str,
        tls_key_path: str,
        tls_ca_path: str,
        db_config: Optional[DatabaseConfig],
        tls_config_getter: Callable[[], Optional[TLSConfigData]],
        auth_grpc_endpoint: Optional[Endpoint],
        frontend_url: Optional[str],
    ):
        self._container = container
        self._tls_cert_path = tls_cert_path
        self._tls_key_path = tls_key_path
        self._tls_ca_path = tls_ca_path
        self._db_config = db_config
        self._tls_config_getter = tls_config_getter
        self._auth_grpc_endpoint = auth_grpc_endpoint
        self._frontend_url = frontend_url
        self._workload_version = get_litmus_version(self._container)

    def reconcile(self):
        """Unconditional control logic."""
        if self._container.can_connect():
            self._reconcile_workload_config()

    def _reconcile_workload_config(self):
        self._patch_manifest_templates()
        self._patch_argo_crds()
        self._container.add_layer(self.layer_name, self._pebble_layer, combine=True)
        # replan only if the available env var config is sufficient for the workload to run
        if self._db_config and self._workload_version:
            self._container.replan()
        else:
            logger.warning(
                "cannot start/restart pebble service: missing database config or workload version.",
            )
            self._container.stop(self.service_name)

    # Argo Workflows 3.4+ removed --container-runtime-executor as a CLI flag
    # and dropped the containerRuntimeExecutor field from the workflow-controller
    # ConfigMap.  The upstream litmuschaos-server still emits both in the
    # Deployment manifests it generates, causing the workflow-controller pod to
    # crash with "unknown field" errors.  We patch the templates in-place before
    # the server starts so neither artefact is written into provisioned infra.
    _MANIFEST_TEMPLATES = (
        "/manifests/namespace/1b_argo_deployment.yaml",
        "/manifests/cluster/1c_argo_deployment.yaml",
    )

    # Argo 3.4.0 introduced WorkflowArtifactGCTask for artifact garbage collection.
    # The upstream litmuschaos-server ships a 3.3-era 1a_argo_crds.yaml that does
    # not include this CRD.  When the workflow-controller starts it tries to watch
    # workflowartifactgctasks resources; because the CRD is absent the informer
    # returns 404 repeatedly, WaitForCacheSync never returns, and the controller's
    # work queue never starts — no workflow is ever processed.
    _ARGO_CRDS_PATH = "/manifests/cluster/1a_argo_crds.yaml"
    _WORKFLOW_ARTIFACT_GC_TASK_CRD = """\
---
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: workflowartifactgctasks.argoproj.io
spec:
  group: argoproj.io
  names:
    kind: WorkflowArtifactGCTask
    listKind: WorkflowArtifactGCTaskList
    plural: workflowartifactgctasks
    shortNames:
    - wfat
    singular: workflowartifactgctask
  scope: Namespaced
  versions:
  - name: v1alpha1
    schema:
      openAPIV3Schema:
        properties:
          apiVersion:
            type: string
          kind:
            type: string
          metadata:
            type: object
          spec:
            type: object
            x-kubernetes-map-type: atomic
            x-kubernetes-preserve-unknown-fields: true
          status:
            type: object
            x-kubernetes-map-type: atomic
            x-kubernetes-preserve-unknown-fields: true
        required:
        - metadata
        - spec
        type: object
    served: true
    storage: true
    subresources:
      status: {}
"""

    def _patch_manifest_templates(self):
        """Strip Argo 3.3 artefacts from Deployment manifest templates."""
        for path in self._MANIFEST_TEMPLATES:
            try:
                content = self._container.pull(path).read()
            except Exception:
                logger.debug("Manifest template not present (yet): %s", path)
                continue
            patched = self._patch_argo_manifest(content)
            if patched != content:
                self._container.push(path, patched)
                logger.info("Patched manifest template for Argo 3.4+ compatibility: %s", path)

    def _patch_argo_crds(self):
        """Add WorkflowArtifactGCTask CRD to the Argo CRDs manifest if absent.

        Argo 3.4.0 introduced this CRD but the Litmus 3.3-era manifests shipped
        with litmuschaos-server do not include it.  The workflow-controller will
        not process any workflows until the CRD exists in the cluster.
        """
        try:
            content = self._container.pull(self._ARGO_CRDS_PATH).read()
        except Exception:
            logger.debug("Argo CRDs manifest not present (yet): %s", self._ARGO_CRDS_PATH)
            return
        if "workflowartifactgctasks.argoproj.io" in content:
            return
        patched = content.rstrip("\n") + "\n" + self._WORKFLOW_ARTIFACT_GC_TASK_CRD
        self._container.push(self._ARGO_CRDS_PATH, patched)
        logger.info("Added WorkflowArtifactGCTask CRD to %s for Argo 3.4+ compatibility", self._ARGO_CRDS_PATH)

    @staticmethod
    def _patch_argo_manifest(content: str) -> str:
        """Remove Argo 3.3-only artefacts from a manifest template string.

        Strips:
        - The ``containerRuntimeExecutor`` ConfigMap key (unknown field in 3.4+)
        - The ``- --container-runtime-executor`` / value arg pair from Deployment args
        """
        lines = content.splitlines(keepends=True)
        result = []
        skip_next = False
        for line in lines:
            if skip_next:
                skip_next = False
                continue
            # ConfigMap key removed in Argo 3.4+
            if line.lstrip().startswith("containerRuntimeExecutor:"):
                continue
            # CLI flag removed in Argo 3.4+ (flag + following value line)
            if "- --container-runtime-executor" in line:
                skip_next = True
                continue
            result.append(line)
        return "".join(result)

    @property
    def _pebble_layer(self) -> Layer:
        """Return a Pebble layer for Litmus backend server."""
        tls_enabled = bool(self._tls_config_getter())
        return Layer(
            {
                "services": {
                    self.service_name: {
                        "override": "replace",
                        "summary": "litmus backend server layer",
                        "command": "/bin/server",
                        "startup": "enabled",
                        "environment": self._environment_vars(tls_enabled),
                    }
                },
                "checks": {
                    self.liveness_check_name: self._pebble_check_layer(tls_enabled)
                },
            }
        )

    @property
    def is_running(self) -> bool:
        """Return True if the backend server is running, False otherwise."""
        try:
            return self._container.get_service(self.service_name).is_running()
        except ConnectionError:
            return False

    def _pebble_check_layer(self, tls_enabled: bool) -> CheckDict:
        return {
            "override": "replace",
            "startup": "enabled",
            "threshold": 3,
            "tcp": {
                "port": self.https_port if tls_enabled else self.http_port,
            },
        }

    def _environment_vars(self, tls_enabled: bool) -> dict:
        workload_version = self._workload_version or ""
        env = {
            "REST_PORT": self.http_port,
            "GRPC_PORT": self.grpc_port,
            "INFRA_DEPLOYMENTS": '["app=chaos-exporter", "name=chaos-operator", "app=workflow-controller", "app=event-tracker"]',
            "DEFAULT_HUB_BRANCH_NAME": "master",  # wokeignore:rule=master
            "ALLOWED_ORIGINS": ".*",
            # k8sapi executor was removed in Argo 3.4.0; emissary is the only executor in 3.4+
            "CONTAINER_RUNTIME_EXECUTOR": "emissary",
            "WORKFLOW_HELPER_IMAGE_VERSION": workload_version,
            # are there other versions we should set along with the current workload version?
            "INFRA_COMPATIBLE_VERSIONS": json.dumps([workload_version]),
            "VERSION": workload_version,
            "SUBSCRIBER_IMAGE": "ghcr.io/canonical/litmusportal-subscriber:dev",
            "EVENT_TRACKER_IMAGE": "ghcr.io/canonical/litmusportal-event-tracker:dev",
            "ARGO_WORKFLOW_CONTROLLER_IMAGE": "charmedkubeflow/workflow-controller:3.4.17-627976f",
            "ARGO_WORKFLOW_EXECUTOR_IMAGE": "charmedkubeflow/argoexec:3.4.17-ae093c9",
            "LITMUS_CHAOS_OPERATOR_IMAGE": "ghcr.io/canonical/chaos-operator:dev",
            "LITMUS_CHAOS_RUNNER_IMAGE": "ghcr.io/canonical/chaos-runner:dev",
            "LITMUS_CHAOS_EXPORTER_IMAGE": "ghcr.io/canonical/chaos-exporter:dev",
        }

        if db_config := self._db_config:
            env.update(
                {
                    "DB_USER": db_config.username,
                    "DB_PASSWORD": db_config.password,
                    "DB_SERVER": db_config.uris,
                }
            )
        if auth_endpoint := self._auth_grpc_endpoint:
            env.update(
                {
                    "LITMUS_AUTH_GRPC_ENDPOINT": auth_endpoint.grpc_server_host,
                    "LITMUS_AUTH_GRPC_PORT": auth_endpoint.grpc_server_port,
                }
            )
        if frontend_url := self._frontend_url:
            env.update(
                {
                    "CHAOS_CENTER_UI_ENDPOINT": frontend_url,
                }
            )
        if tls_enabled:
            env.update(
                {
                    "ENABLE_INTERNAL_TLS": "true",
                    "REST_PORT": self.https_port,
                    "GRPC_PORT": self.grpc_tls_port,
                    "TLS_CERT_PATH": self._tls_cert_path,
                    "TLS_KEY_PATH": self._tls_key_path,
                    "CA_CERT_TLS_PATH": self._tls_ca_path,
                }
            )

        return env

    @property
    def litmus_backend_ports(self) -> tuple[int, int]:
        if not self._tls_config_getter():
            return self.http_port, self.grpc_port
        return self.https_port, self.grpc_tls_port
