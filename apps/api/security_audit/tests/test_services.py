from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.db.transaction import TransactionManagementError
from django.test import TestCase

from security_audit.models import SecurityAuditEvent
from security_audit.services import record_critical_event, record_denied_event_best_effort, record_security_event

from .factories import user_factory


class AuditServiceTests(TestCase):
    def valid_fields(self, **overrides):
        fields = {
            "action": SecurityAuditEvent.Action.ACCOUNT_DEACTIVATED,
            "actor_user_id": 17,
            "target_type": SecurityAuditEvent.TargetType.ACCOUNT,
            "target_id": "42",
            "outcome": SecurityAuditEvent.Outcome.SUCCESS,
            "request_id": "123e4567-e89b-42d3-a456-426614174000",
        }
        fields.update(overrides)
        return fields

    def denied_fields(self, **overrides):
        fields = self.valid_fields(**overrides)
        fields.pop("outcome")
        return fields

    def test_records_structured_event_with_immutable_actor_snapshot(self):
        event = record_security_event(**self.valid_fields())
        event.refresh_from_db()
        self.assertEqual(event.actor_user_id, 17)
        self.assertEqual(event.action, SecurityAuditEvent.Action.ACCOUNT_DEACTIVATED)
        self.assertEqual(event.target_id, "42")
        self.assertEqual(event.outcome, SecurityAuditEvent.Outcome.SUCCESS)
        self.assertIsNotNone(event.occurred_at)

    def test_event_model_rejects_update_and_delete(self):
        event = record_security_event(**self.valid_fields())
        event.outcome = SecurityAuditEvent.Outcome.FAILURE
        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            event.delete()

    def test_service_signature_rejects_non_allowlisted_fields(self):
        forbidden = ("password", "token", "cookie", "session_id", "email", "ip_address", "payload")
        for field in forbidden:
            with self.subTest(field=field):
                with self.assertRaises(TypeError):
                    record_security_event(**self.valid_fields(**{field: "SENTINEL-SECRET"}))
        self.assertFalse(SecurityAuditEvent.objects.exists())

    def test_identifiers_reject_secret_shaped_or_free_text_values_without_logging_them(self):
        sentinels = ("secret value", "a/b", "user@example.test", "token=abc", "line\nbreak")
        with self.assertLogs("security_audit.services", level="WARNING") as captured:
            for sentinel in sentinels:
                self.assertIsNone(record_denied_event_best_effort(**{
                    **self.denied_fields(target_id=sentinel),
                }))
        rendered = " ".join(captured.output)
        for sentinel in sentinels:
            self.assertNotIn(sentinel, rendered)
        self.assertFalse(SecurityAuditEvent.objects.exists())

    def test_controlled_vocabularies_and_actor_validation(self):
        invalid = ({"action": "custom.action"}, {"target_type": "email"}, {"outcome": "maybe"}, {"actor_user_id": -1})
        for values in invalid:
            with self.subTest(values=values):
                with self.assertRaises(ValidationError):
                    record_security_event(**self.valid_fields(**values))

    def test_audit_failure_rolls_back_security_critical_mutation(self):
        target = user_factory(is_active=True)
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                target.is_active = False
                target.save(update_fields=("is_active",))
                with patch("security_audit.models.SecurityAuditEvent.save", side_effect=DatabaseError("sentinel")):
                    record_critical_event(**self.valid_fields(target_id=str(target.pk)))
        target.refresh_from_db()
        self.assertTrue(target.is_active)
        self.assertFalse(SecurityAuditEvent.objects.exists())

    def test_critical_event_requires_caller_transaction(self):
        with patch("security_audit.services.connection.in_atomic_block", False):
            with self.assertRaises(TransactionManagementError):
                record_critical_event(**self.valid_fields())

    def test_denied_attempt_failure_is_one_attempt_and_safe(self):
        with patch("security_audit.services.record_security_event", side_effect=DatabaseError("SENTINEL-SECRET")) as recorder:
            with self.assertLogs("security_audit.services", level="WARNING") as captured:
                result = record_denied_event_best_effort(**{
                    **self.denied_fields(),
                })
        self.assertIsNone(result)
        recorder.assert_called_once()
        self.assertNotIn("SENTINEL-SECRET", " ".join(captured.output))
