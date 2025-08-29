# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charmed Operator for Litmus Chaoscenter; the frontend for a chaos testing platform."""

import logging

from ops.charm import CharmBase
from ops import (
    LifecycleEvent,
    EventBase,
    CollectStatusEvent,
    BlockedStatus,
    WaitingStatus,
    ActiveStatus,
)

from litmus_frontend import LitmusFrontend
from litmus_libs import get_app_hostname
from litmus_libs.interfaces.http_api import (
    LitmusAuthApiRequirer,
    LitmusBackendApiRequirer,
)

logger = logging.getLogger(__name__)
AUTH_HTTP_API_ENDPOINT = "auth-http-api"
BACKEND_HTTP_API_ENDPOINT = "backend-http-api"


class LitmusChaoscenterCharm(CharmBase):
    """Charmed Operator for Litmus Chaoscenter."""

    def __init__(self, *args):
        super().__init__(*args)
        self._receive_auth_http_api = LitmusAuthApiRequirer(
            relation=self.model.get_relation(AUTH_HTTP_API_ENDPOINT), app=self.app
        )
        self._receive_backend_http_api = LitmusBackendApiRequirer(
            relation=self.model.get_relation(BACKEND_HTTP_API_ENDPOINT), app=self.app
        )

        self.litmus_frontend = LitmusFrontend(
            container=self.unit.get_container(LitmusFrontend.name),
            backend_url=self.backend_url,
        )

        self.framework.observe(
            self.on.collect_unit_status, self._on_collect_unit_status
        )

        for event in self.on.events().values():
            # ignore LifecycleEvents: we want to execute the reconciler exactly once per juju hook.
            if issubclass(event.event_type, LifecycleEvent):
                continue
            self.framework.observe(event, self._on_any_event)

    ##################
    # EVENT HANDLERS #
    ##################
    @property
    def _frontend_url(self):
        """Internal (i.e. not ingressed) url."""
        # TODO: add support for HTTPS once https://github.com/canonical/litmus-operators/issues/23 is fixed
        # TODO: add nginx port instead of 8080
        return f"http://{get_app_hostname(self.app.name, self.model.name)}:8080"

    @property
    def backend_url(self):
        """The backend's http API url."""
        return self._receive_backend_http_api.backend_endpoint

    def _on_any_event(self, _: EventBase):
        """Common entry hook."""
        self._reconcile()
        self._receive_backend_http_api.publish_endpoint(self._frontend_url)

    def _on_collect_unit_status(self, e: CollectStatusEvent):
        missing_relations = [
            rel
            for rel in (AUTH_HTTP_API_ENDPOINT, BACKEND_HTTP_API_ENDPOINT)
            if not self.model.get_relation(rel)
        ]
        missing_configs = [
            config_name
            for config_name, source in (
                ("backend http API endpoint url", self.backend_url),
            )
            if not source
        ]
        if missing_relations:
            e.add_status(
                BlockedStatus(
                    f"Missing [{', '.join(missing_relations)}] integration(s)."
                )
            )
        if missing_configs:
            e.add_status(
                WaitingStatus(f"[{', '.join(missing_configs)}] not provided yet.")
            )

        # TODO: add pebble check to verify frontend is up
        e.add_status(ActiveStatus(f"Ready at {self._frontend_url}."))

    ###################
    # UTILITY METHODS #
    ###################
    def _reconcile(self):
        """Run all logic that is independent of what event we're processing."""
        self.litmus_frontend.reconcile()


if __name__ == "__main__":  # pragma: nocover
    from ops import main

    main(LitmusChaoscenterCharm)  # noqa
