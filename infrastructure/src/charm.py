# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charmed Operator for Litmus Infrastructure; signals the Litmus ChaosCenter to create the infrastructure components required to run chaos experiments"""

import subprocess
import logging
from pathlib import Path
from opentelemetry import trace

from ops.charm import CharmBase

from cosl.reconciler import all_events, observe_events
from ops import ActiveStatus, CollectStatusEvent
from litmus_libs.status_manager import StatusManager
from litmus_libs.interfaces.litmus_infrastructure import (
    LitmusInfrastructureProvider,
    InfrastructureDatabagModel,
)
import ops_tracing
from charms.tempo_coordinator_k8s.v0.tracing import TracingEndpointRequirer
from charms.certificate_transfer_interface.v1.certificate_transfer import (
    CertificateTransferRequires,
)

logger = logging.getLogger(__name__)

_tracer = trace.get_tracer("litmus_infrastructure.tracer")

TRUSTED_CA_CERT_PATH = Path("/usr/local/share/ca-certificates/trusted-ca-cert.crt")


class LitmusInfrastructureCharm(CharmBase):
    """Charmed Operator for Litmus Infrastructure."""

    def __init__(self, *args):
        super().__init__(*args)
        self._infra_provider = LitmusInfrastructureProvider(
            self.model.relations["litmus-infrastructure"],
            self.app,
            self.unit,
        )
        self._charm_tracing = TracingEndpointRequirer(
            self,
            relation_name="charm-tracing",
            protocols=["otlp_http"],
        )
        self._trusted_cert_transfer = CertificateTransferRequires(
            self, "receive-ca-certs"
        )

        self.framework.observe(
            self.on.collect_unit_status, self._on_collect_unit_status
        )

        observe_events(self, all_events, self._reconcile)

    ##################
    # EVENT HANDLERS #
    ##################

    def _on_collect_unit_status(self, e: CollectStatusEvent):
        StatusManager(
            charm=self,
            block_if_relations_missing=("litmus-infrastructure",),
        ).collect_status(e)
        e.add_status(ActiveStatus(""))

    ###################
    # UTILITY METHODS #
    ###################

    @property
    def _trusted_ca_certs(self) -> str | None:
        if certs := self._trusted_cert_transfer.get_all_certificates():
            return "\n".join(sorted(certs))
        return None

    def _reconcile(self):
        """Run all logic that is independent of what event we're processing."""
        self._reconcile_trusted_certs()
        self._reconcile_charm_tracing()

        if self.unit.is_leader():
            self._infra_provider.publish_data(
                InfrastructureDatabagModel(
                    # for now, we can set the infra name as the model name
                    infrastructure_name=self.model.name,
                    model_name=self.model.name,
                )
            )

    def _reconcile_trusted_certs(self):
        if certificates := self._trusted_ca_certs:
            curr = (
                TRUSTED_CA_CERT_PATH.read_text()
                if TRUSTED_CA_CERT_PATH.exists()
                else ""
            )
            if curr != certificates:
                with _tracer.start_as_current_span("update trusted certs"):
                    TRUSTED_CA_CERT_PATH.parent.mkdir(parents=True, exist_ok=True)
                    TRUSTED_CA_CERT_PATH.write_text(certificates)
                    subprocess.run(["update-ca-certificates", "--fresh"])
        else:
            if TRUSTED_CA_CERT_PATH.exists():
                with _tracer.start_as_current_span("remove trusted certs"):
                    TRUSTED_CA_CERT_PATH.unlink(missing_ok=True)

    def _reconcile_charm_tracing(self):
        if self._charm_tracing.is_ready():
            endpoint = self._charm_tracing.get_endpoint("otlp_http")
            if not endpoint:
                return
            ops_tracing.set_destination(
                url=endpoint + "/v1/traces",
                ca=self._trusted_ca_certs,
            )


if __name__ == "__main__":  # pragma: nocover
    from ops import main

    main(LitmusInfrastructureCharm)  # noqa
