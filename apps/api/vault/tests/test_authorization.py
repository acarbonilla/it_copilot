from unittest.mock import patch

from django.test import SimpleTestCase

from vault.authorization import SensitiveAuthorization
from vault.services import VaultSensitiveAuthorizationRequired, _require_sensitive
from vault.testing import (
    authorize_sensitive_operation_for_test,
    patch_sensitive_authorization_for_test,
)


class FakeActor:
    pk = 42


class VaultAuthorizationIsolationTests(SimpleTestCase):
    def test_production_authorization_cannot_be_constructed(self):
        with self.assertRaises(PermissionError):
            SensitiveAuthorization()

    def test_production_service_rejects_missing_and_test_authorization(self):
        actor = FakeActor()
        proof = authorize_sensitive_operation_for_test(actor)
        with patch("vault.services._audit_unavailable"):
            for authorization in (None, proof, object()):
                with self.subTest(authorization=type(authorization).__name__):
                    with self.assertRaises(VaultSensitiveAuthorizationRequired):
                        _require_sensitive(actor, authorization)


    def test_explicit_mock_harness_is_owner_bound(self):
        actor = FakeActor()
        proof = authorize_sensitive_operation_for_test(actor)

        with patch_sensitive_authorization_for_test():
            from vault import services

            services._require_sensitive(actor, proof)

            with self.assertRaises(
                VaultSensitiveAuthorizationRequired
            ):
                services._require_sensitive(
                    type("Other", (), {"pk": 43})(),
                    proof,
                )

            with self.assertRaises(
                VaultSensitiveAuthorizationRequired
            ):
                services._require_sensitive(actor, None)


    def test_invalid_test_actor_ids(self):
        for actor_id in (None, 0, -1, True, "42"):
            with self.subTest(actor_id=actor_id):
                with self.assertRaises(ValueError):
                    authorize_sensitive_operation_for_test(
                        type("Actor", (), {"pk": actor_id})()
                    )
