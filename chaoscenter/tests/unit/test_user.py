# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for user_manager.UserManager."""

import logging
from unittest.mock import MagicMock, patch, call

import pytest
from ops import Secret

from user_manager import UserManager


VALID_SECRET_CONTENT = {
    "admin_password": "adminpass",
    "charm_password": "charmpass",
}

INVALID_SECRET_CONTENT = {
    "admin_password": "adminpass",
    # missing charm_password
}


def _make_secret(current: dict, next_: dict | None = None) -> MagicMock:
    """Create a mock Secret with get_content and peek_content returning the given dicts."""
    secret = MagicMock(spec=Secret)
    secret.get_content.return_value = current
    secret.peek_content.return_value = next_ if next_ is not None else current
    return secret


def _make_user_manager(secret_id: str | None, secret: Secret | None = None) -> UserManager:
    get_secret = MagicMock(return_value=secret)
    litmusctl = MagicMock()
    return UserManager(secret_id=secret_id, get_secret=get_secret, litmusctl=litmusctl), get_secret


class TestSecretResolution:
    """Tests for the secret resolution logic (_secret property)."""

    def test_no_secret_id_returns_none(self):
        # GIVEN no secret id is configured
        um, get_secret = _make_user_manager(secret_id=None)

        # WHEN reconcile is called
        # THEN the get_secret callable is never called (no secret to look up)
        um.reconcile()
        get_secret.assert_not_called()

    def test_invalid_secret_id_format_logs_warning(self, caplog):
        # GIVEN a secret id that does not start with "secret:"
        um, get_secret = _make_user_manager(secret_id="not-a-secret-id")

        # WHEN reconcile is called
        with caplog.at_level(logging.WARNING, logger="user_manager"):
            um.reconcile()

        # THEN a warning is logged and get_secret is not called
        assert any("Invalid secret identifier" in m for m in caplog.messages)
        get_secret.assert_not_called()

    def test_secret_not_found_in_model_logs_warning(self, caplog):
        # GIVEN a valid secret id but the secret does not exist in the model
        um, get_secret = _make_user_manager(secret_id="secret:abc123", secret=None)

        # WHEN reconcile is called
        with caplog.at_level(logging.WARNING, logger="user_manager"):
            um.reconcile()

        # THEN a warning is logged
        assert any("not found in model" in m for m in caplog.messages)

    def test_valid_secret_id_passed_to_get_secret(self):
        # GIVEN a valid secret id and a secret that exists
        secret = _make_secret(VALID_SECRET_CONTENT)
        um, get_secret = _make_user_manager(secret_id="secret:abc123", secret=secret)

        # WHEN reconcile is called
        um.reconcile()

        # THEN the get_secret callable is called with the configured secret id
        get_secret.assert_called_once_with("secret:abc123")


class TestReconcileUnchangedCredentials:
    """Tests for reconcile() when secret content has not changed."""

    def test_valid_unchanged_credentials_attempts_apply(self):
        # GIVEN a valid secret where current == next (no change)
        secret = _make_secret(VALID_SECRET_CONTENT)
        um, _ = _make_user_manager(secret_id="secret:abc123", secret=secret)

        # WHEN reconcile is called
        with patch.object(um, "_apply_credentials", return_value=False) as mock_apply:
            um.reconcile()

        # THEN apply_credentials is called with the current credentials
        mock_apply.assert_called_once()

    def test_invalid_unchanged_credentials_logs_warning(self, caplog):
        # GIVEN a secret with invalid contents that has not changed
        secret = _make_secret(INVALID_SECRET_CONTENT)
        um, _ = _make_user_manager(secret_id="secret:abc123", secret=secret)

        # WHEN reconcile is called
        with caplog.at_level(logging.WARNING, logger="user_manager"):
            um.reconcile()

        # THEN a warning is logged and credentials are not applied
        assert any("invalid secret contents" in m for m in caplog.messages)

    def test_apply_failure_does_not_refresh_secret(self):
        # GIVEN a valid secret where apply_credentials fails
        secret = _make_secret(VALID_SECRET_CONTENT)
        um, _ = _make_user_manager(secret_id="secret:abc123", secret=secret)

        # WHEN reconcile is called and apply fails
        with patch.object(um, "_apply_credentials", return_value=False):
            um.reconcile()

        # THEN the secret is never refreshed
        secret.get_content.assert_called_once_with(refresh=False)


class TestReconcileChangedCredentials:
    """Tests for reconcile() when the secret has a new revision."""

    def test_changed_valid_credentials_applies_new_creds(self):
        # GIVEN a secret whose content has changed to valid new credentials
        new_content = {"admin_password": "newadmin", "charm_password": "newcharm"}
        secret = _make_secret(current=VALID_SECRET_CONTENT, next_=new_content)
        um, _ = _make_user_manager(secret_id="secret:abc123", secret=secret)

        # WHEN reconcile is called and apply succeeds
        with patch.object(um, "_apply_credentials", return_value=True) as mock_apply:
            um.reconcile()

        # THEN apply is called with the new credentials
        mock_apply.assert_called_once()
        applied_creds = mock_apply.call_args[0][0]
        assert applied_creds.admin_password == "newadmin"
        assert applied_creds.charm_password == "newcharm"

    def test_changed_valid_credentials_refreshes_secret_on_success(self):
        # GIVEN a secret whose content has changed to valid new credentials
        new_content = {"admin_password": "newadmin", "charm_password": "newcharm"}
        secret = _make_secret(current=VALID_SECRET_CONTENT, next_=new_content)
        um, _ = _make_user_manager(secret_id="secret:abc123", secret=secret)

        # WHEN reconcile is called and apply succeeds
        with patch.object(um, "_apply_credentials", return_value=True):
            um.reconcile()

        # THEN the secret is refreshed to track the new revision
        secret.get_content.assert_any_call(refresh=True)

    def test_changed_valid_credentials_does_not_refresh_on_apply_failure(self):
        # GIVEN a secret whose content has changed to valid new credentials
        new_content = {"admin_password": "newadmin", "charm_password": "newcharm"}
        secret = _make_secret(current=VALID_SECRET_CONTENT, next_=new_content)
        um, _ = _make_user_manager(secret_id="secret:abc123", secret=secret)

        # WHEN reconcile is called but apply fails
        with patch.object(um, "_apply_credentials", return_value=False):
            um.reconcile()

        # THEN the secret is NOT refreshed
        assert call(refresh=True) not in secret.get_content.call_args_list

    def test_changed_invalid_credentials_does_not_apply(self, caplog):
        # GIVEN a secret whose new revision contains invalid credentials
        secret = _make_secret(current=VALID_SECRET_CONTENT, next_=INVALID_SECRET_CONTENT)
        um, _ = _make_user_manager(secret_id="secret:abc123", secret=secret)

        # WHEN reconcile is called
        with patch.object(um, "_apply_credentials") as mock_apply:
            with caplog.at_level(logging.WARNING, logger="user_manager"):
                um.reconcile()

        # THEN apply is never called and a warning is logged
        mock_apply.assert_not_called()
        assert any("invalid secret contents" in m for m in caplog.messages)


class TestValidateSecretContent:
    """Tests for _validate_secret_content."""

    def test_valid_content_returns_true(self):
        assert UserManager._validate_secret_content(VALID_SECRET_CONTENT) is True

    def test_missing_field_returns_false(self):
        assert UserManager._validate_secret_content(INVALID_SECRET_CONTENT) is False

    def test_empty_content_returns_false(self):
        assert UserManager._validate_secret_content({}) is False

    def test_extra_fields_are_allowed(self):
        content = {**VALID_SECRET_CONTENT, "extra_field": "ignored"}
        assert UserManager._validate_secret_content(content) is True
