"""Litmus charms status collection utilities."""
from typing import Any, Iterable, Sequence

import ops
from ops.pebble import CheckStatus


class StatusManager:
    """Set the appropriate status on a collect status event."""
    _relations_missing_msg_template = "Missing [{}] integration(s)."
    _configs_missing_msg_template = "Required configurations [{}] not ready yet."
    _checks_failing_msg_template = "Pebble checks [{}] are 'DOWN'."

    def __init__(self,
                 charm: ops.CharmBase,
                 wait_for_config: dict[str, Any|None] | None = None,
                 block_if_relations_missing: Iterable[str]|None = None,
                 block_if_pebble_checks_failing: dict[str, Sequence[str]]|None = None,
                 ):
        self._wait_for_config = wait_for_config or {}
        self._block_if_relations_missing = block_if_relations_missing or ()
        self._block_if_pebble_checks_failing = block_if_pebble_checks_failing or {}
        self._charm = charm

    def collect_status(self, e:ops.CollectStatusEvent):
        """Check the status."""
        for status in filter(None, (
            self._blocked_if_relations_missing(),
            self._waiting_if_configs_missing(),
            self._blocked_if_pebble_checks_failing()
        )):
            e.add_status(status)

    def _blocked_if_relations_missing(self)->ops.StatusBase|None:
        """Set blocked status if any required relation is missing."""
        missing_relations = [
            rel
            for rel in self._block_if_relations_missing
            if not self._charm.model.get_relation(rel)
        ]
        if missing_relations:
            return ops.BlockedStatus(self._relations_missing_msg_template.format(", ".join(missing_relations)))
        return None

    def _waiting_if_configs_missing(self)->ops.StatusBase|None:
        """Set waiting status if any required config is missing."""
        missing_configs = [
            config_name
            for config_name, source in self._wait_for_config.items()
            if source is None
        ]
        if missing_configs:
            return ops.WaitingStatus(self._configs_missing_msg_template.format(', '.join(missing_configs)))
        return None

    def _blocked_if_pebble_checks_failing(self)->ops.StatusBase|None:
        """Set blocked status if any pebble check is not reporting UP."""
        failing_checks: list[str] = []
        for container_name, checks in self._block_if_pebble_checks_failing.items():
            container = self._charm.unit.get_container(container_name)
            checks_status = container.get_checks(*checks)
            for check_name, check_status in checks_status.items():
                if check_status.status is CheckStatus.DOWN:
                    failing_checks.append(check_name)

        if failing_checks:
            return ops.BlockedStatus(self._checks_failing_msg_template.format(", ".join(failing_checks)))
        return None
