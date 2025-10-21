from typing import Optional, Dict


class TLSConsistency:
    """Helper class to manage tls consistency logic."""
    def __init__(self, any_remote_on_tls:bool, local_on_tls):
        self._any_remote_on_tls = any_remote_on_tls
        self._local_on_tls = local_on_tls

    @property
    def is_consistent(self) -> bool:
        """Check if this charm's current configuration is inconsistent."""
        if self._any_remote_on_tls and not self._local_on_tls:
            return False
        return True

    @property
    def requires_tls_relation(self) -> bool:
        """Check if this charm's current configuration requires a tls certificates relation to be consistent."""
        return not self.is_consistent

    @property
    def missing_configs(self) -> Dict[str, Optional[bool]]:
        """Missing configurations; to be passed to a StatusManager."""
        if self.is_consistent:
            return {}
        return {"tls certificate": None}
