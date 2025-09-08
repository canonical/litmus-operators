# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charmed Operator for Litmus Chaoscenter; the frontend for a chaos testing platform."""

import logging
import socket

from ops.charm import CharmBase
from ops import (
    LifecycleEvent,
    EventBase,
    CollectStatusEvent,
    BlockedStatus,
    WaitingStatus,
    ActiveStatus,
)
from coordinated_workers.nginx import (
    Nginx,
)

from nginx_config import get_config

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

        self.nginx = Nginx(
            self,
            config_getter=self._nginx_config,
            # TODO https://github.com/canonical/litmus-operators/issues/39
            tls_config_getter=lambda: None,
            options=None,
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
    # CONFIG METHODS #
    ##################

    def _nginx_config(self, tls: bool) -> str:
        # TODO add support for TLS https://github.com/canonical/litmus-operators/issues/39
        return get_config(socket.getfqdn(), self.auth_url, self.backend_url)

    ##################
    # EVENT HANDLERS #
    ##################
    @property
    def _frontend_url(self):
        """Internal (i.e. not ingressed) url."""
        # TODO: add support for HTTPS once https://github.com/canonical/litmus-operators/issues/23 is fixed
        return f"http://{get_app_hostname(self.app.name, self.model.name)}:8185"

    @property
    def backend_url(self):
        """The backend's http API url."""
        return self._receive_backend_http_api.backend_endpoint

    @property
    def auth_url(self):
        """The auth's http API url."""
        return self._receive_auth_http_api.auth_endpoint

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
                ("auth http API endpoint url", self.auth_url),
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
        #  https://github.com/canonical/litmus-operators/issues/36
        e.add_status(ActiveStatus(f"Ready at {self._frontend_url}."))

    ###################
    # UTILITY METHODS #
    ###################
    def _reconcile(self):
        """Run all logic that is independent of what event we're processing."""
        if self.backend_url and self.auth_url:
            self.nginx.reconcile()


if __name__ == "__main__":  # pragma: nocover
    from ops import main

    main(LitmusChaoscenterCharm)  # noqa
