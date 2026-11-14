"""Test-only support for IC-021 service behavior verification.

This module is imported only by tests. It does not mint production
SensitiveAuthorization objects or modify production authorization code.
"""
from dataclasses import dataclass
from unittest.mock import patch


@dataclass(frozen=True)
class TestSensitiveAuthorization:
    actor_id: int


def authorize_sensitive_operation_for_test(actor):
    actor_id = getattr(actor, "pk", None)
    if type(actor_id) is not int or actor_id <= 0:
        raise ValueError("A persisted test actor is required")
    return TestSensitiveAuthorization(actor_id)


def _test_require_sensitive(actor, authorization):
    from vault.services import VaultSensitiveAuthorizationRequired
    actor_id = getattr(actor, "pk", None)
    if (
        not isinstance(authorization, TestSensitiveAuthorization)
        or type(actor_id) is not int
        or authorization.actor_id != actor_id
    ):
        raise VaultSensitiveAuthorizationRequired(
            "Sensitive vault operation is unavailable"
        )


def patch_sensitive_authorization_for_test():
    """Explicit unittest mock context; production code never calls this."""
    return patch("vault.services._require_sensitive", side_effect=_test_require_sensitive)
