# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""This module defines the UserManager class, which is responsible for managing user credentials for all charm-owned
and default accounts. It retrieves credentials from a specified secret, validates them, and applies them to the
system as needed.

The idea is: the charm administrator will create a secret, grant it to the chaoscenter app, and the
charm will use the credentials in that secret to set up the admin user and the 'charm' bot account in the system.
Given that we cannot disable the behaviour that forces the user to update their passwords on first login, we
set an initial random password for both accounts and then set the password to whatever the user passed
in the user secret.

When the secret changes, the charm will validate the new credentials and apply them.
This guarantees that if the user deletes the chaoscenter, the credentials will be persisted in the
user secret. And when they re-deploy the charm and pass in the same secret, their credentials will be the same as before,
which means the data in the database will still be accessible.
"""

import logging
import secrets
from typing import Optional, Dict, Callable
import pydantic

from ops import Secret

from litmus_client import LitmusClient, DEFAULT_ADMIN_PASSWORD

logger = logging.getLogger(__name__)


class _UserSecretModel(pydantic.BaseModel):
    """Pydantic model representing the expected structure of the secret containing user credentials."""
    admin_password: str
    charm_password: str


class UserManager:
    """Manages user operations for all charm-owned and default accounts."""

    # Name of the bot account the charm uses for internal operations.
    CHARM_USERNAME = "charm"

    def __init__(
        self,
        secret_id: Optional[str],
        get_secret: Callable[[str], Optional[Secret]],
        make_client: Callable[[str, str], LitmusClient],
    ):
        self._secret_id = secret_id
        self._get_secret = get_secret
        self._make_client = make_client

    @property
    def _secret(self) -> Optional[Secret]:
        """The secret containing user credentials for the admin and the 'charm' bot account."""
        secret_id = self._secret_id
        if not secret_id:
            return None
        if not secret_id.startswith("secret:"):
            logger.warning(
                f"Invalid secret identifier '{secret_id}' in config; expected format 'secret:<...>'"
            )
            return None
        secret = self._get_secret(secret_id)
        if not secret:
            logger.warning(
                f"Secret '{secret_id}' not found in model; ensure the secret exists, was granted to this application, "
                f"and the identifier is correct"
            )
            return None
        return secret

    @staticmethod
    def _validate_secret_content(content: Dict[str, str]) -> bool:
        # validate secret contents
        try:
            _UserSecretModel.model_validate(content)
        except pydantic.ValidationError:
            logger.exception("invalid secret contents")
            return False
        return True

    def reconcile(self):
        """Verify that the secret is valid and the currently set credentials are up to date.


        """

        secret = self._secret
        if not secret:
            return

        # current credentials
        current_creds = secret.get_content(refresh=False)
        # 'next' credentials (if changed)
        next_creds = secret.peek_content()

        # if the credentials have changed since the last time we applied them, validate and apply the new credentials
        if current_creds != next_creds:
            logger.info("secret contents have changed from earlier revision; validating new credentials")
            if not self._validate_secret_content(next_creds):
                logger.warning("invalid secret contents; ignoring changes")
                return

            creds = _UserSecretModel.model_validate(next_creds)

            logger.info("secret contents are valid; updating credentials")
            # first try to apply them; if it fails we don't refresh the secret, so next time we'll try again
            if self._apply_credentials(creds):
                logger.debug("successfully updated user credentials")
                secret.get_content(refresh=True)

            else:
                logger.warning("failed to apply new credentials; will retry on next reconcile")

        # else: either credentials haven't changed, or this is the first time we're reconciling.
        # if the latter, we need to apply the credentials, else it's a no-op.
        # since we can't quite tell, we attempt to apply them: the API calls are idempotent
        # (login succeeds if credentials are already correct; user creation is skipped if user exists).
        else:
            logger.info("secret contents have not changed since last revision; ensuring credentials are applied")
            if self._validate_secret_content(current_creds):
                creds = _UserSecretModel.model_validate(current_creds)
                if self._apply_credentials(creds):
                    logger.debug("successfully applied user credentials")
                else:
                    logger.warning("failed to apply user credentials; will retry on next reconcile")
            else:
                logger.warning("invalid secret contents; cannot apply credentials")

    def _apply_credentials(self, creds: _UserSecretModel) -> bool:
        """Apply the given credentials to the system. Returns True if successful, False otherwise."""
        logger.debug("applying user credentials via Litmus API")
        try:
            self._ensure_admin_password(creds.admin_password)
            self._ensure_charm_user(creds.admin_password, creds.charm_password)
        except Exception:
            logger.exception("failed to apply user credentials")
            return False
        return True

    def _ensure_admin_password(self, target_password: str) -> None:
        """Ensure the admin account uses target_password.

        Litmus ships with a default admin password ("litmus"). On first deployment the charm
        resets it from the Litmus default to the value in the secret. On subsequent reconciles
        a successful login with target_password is a no-op.
        """
        client = self._make_client("admin", target_password)
        if client.can_login():
            logger.debug("admin credentials already correct")
            return

        # Not logged in with target password – try the Litmus factory default.
        logger.info("admin login with target password failed; attempting reset from default password")
        default_client = self._make_client("admin", DEFAULT_ADMIN_PASSWORD)
        default_client.set_password(DEFAULT_ADMIN_PASSWORD, target_password)
        logger.info("admin password updated successfully")

    def _ensure_charm_user(self, admin_password: str, charm_password: str) -> None:
        """Ensure the charm bot account exists with charm_password.

        If the user does not yet exist it is created with a random temporary password and
        immediately reset to charm_password (bypassing the forced-reset-on-first-login
        restriction in Litmus).
        """
        admin = self._make_client("admin", admin_password)

        if not admin.user_exists(self.CHARM_USERNAME):
            logger.info("charm user does not exist; creating with temporary password")
            temp_password = secrets.token_urlsafe(16)
            admin.create_user(self.CHARM_USERNAME, temp_password)
            charm = self._make_client(self.CHARM_USERNAME, temp_password)
            charm.set_password(temp_password, charm_password)
            logger.info("charm user created and password set")
            return

        charm = self._make_client(self.CHARM_USERNAME, charm_password)
        if charm.can_login():
            logger.debug("charm credentials already correct")
        else:
            raise Exception(
                "charm user exists but login with the configured password failed; "
                "ensure the secret contains the correct current charm password"
            )