# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import Callable

import ops
from ops import Secret

from litmusctl import Litmusctl
from user_manager import UserManager


class Chaoscenter:
    """Represents the Chaoscenter workload state and encapsulates all logic to operate it."""

    def __init__(self,
                 user_secret_id: str,
                 get_secret: Callable[[str], Secret],
                 container: ops.Container):
        self._cli = cli = Litmusctl(container)
        self._user_manager = UserManager(user_secret_id, get_secret, cli)

    def reconcile(self):
        """Reconcile the state of the application, ensuring that all components are in their desired state."""
        self._user_manager.reconcile()