# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.


from typing import Callable, Optional
from ops import Secret

import environment_manager
from infra_manager import InfraManager
from litmus_client import LitmusClient
from user_manager import UserManager
from litmus_libs.interfaces.litmus_infrastructure import (
    InfrastructureDatabagModel,
)


class Chaoscenter:
    """Represents the Chaoscenter workload state and encapsulates all logic to operate it."""

    def __init__(
        self,
        endpoint: str,
        user_secret_id: Optional[str],
        get_secret: Callable[[str], Secret],
        infra_data: list[InfrastructureDatabagModel],
    ):

        self._user_manager = UserManager(
            secret_id=user_secret_id,
            get_secret=get_secret,
            make_client=lambda username, password: LitmusClient(
                endpoint=endpoint, username=username, password=password
            ),
        )

        self._infra_manager = InfraManager(infra_data)

    @property
    def user_secrets_valid(self) -> bool:
        """Returns True if the UserManager is ready to manage credentials, False otherwise."""
        return self._user_manager.user_secrets_valid

    def reconcile(self):
        """Reconcile the state of the application, ensuring that all components are in their desired state."""
        self._user_manager.reconcile()

        # Only attempt to reconcile env/infra if we have valid credentials
        client = self._user_manager.get_charm_client()
        if client is None or not client.can_login():
            return

        environment_manager.reconcile(client)
        self._infra_manager.reconcile(client)
