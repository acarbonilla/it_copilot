import base64
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import User
from security_audit.models import SecurityAuditEvent
from security_audit.services import record_critical_event, record_denied_event_best_effort

from .authorization import SensitiveAuthorization
from .crypto import (
    EncryptionContext,
    EncryptionEnvelope,
    VaultCryptoError,
    WrappedKeyEnvelope,
    decrypt,
    encrypt,
    unwrap_dek,
    wrap_dek,
)
from .keys import load_kek
from .models import DEK_BYTES, VaultOwnerKey, VaultRecord


MAX_RECORDS_PER_OWNER = 1_000
RESTORE_WINDOW_DAYS = 30
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


class VaultUnavailableError(PermissionDenied):
    pass


class VaultConflictError(Exception):
    pass


class VaultSensitiveAuthorizationRequired(PermissionDenied):
    pass


class VaultServiceUnavailable(Exception):
    pass


@dataclass
class DeferredReveal:
    """Plaintext holder that cannot release until the critical transaction commits."""

    _payload: dict
    _committed: bool = False

    def _mark_committed(self):
        self._committed = True

    def release(self):
        if not self._committed:
            raise VaultServiceUnavailable("Vault reveal is unavailable")
        return dict(self._payload)

    def discard(self):
        self._payload.clear()
        self._committed = False


@dataclass(frozen=True)
class CredentialPage:
    records: list
    next_cursor: str | None


def _actor_id(actor):
    value = getattr(actor, "pk", None)
    return value if isinstance(value, int) and value > 0 else None


def _audit_unavailable(actor):
    record_denied_event_best_effort(
        action=SecurityAuditEvent.Action.AUTHORIZATION_DENIED,
        actor_user_id=_actor_id(actor),
        target_type=SecurityAuditEvent.TargetType.PRIVATE_RESOURCE,
        target_id=None,
    )


def _active_actor(actor, *, lock=False):
    actor_id = _actor_id(actor)
    if actor_id is None:
        return None
    queryset = User.objects.select_for_update() if lock else User.objects
    return queryset.filter(pk=actor_id, is_active=True).exclude(lifecycle_state=User.LifecycleState.DEACTIVATED).first()


def _require_sensitive(actor, authorization):
    actor_id = _actor_id(actor)
    if not isinstance(authorization, SensitiveAuthorization) or not authorization.valid_for(actor_id):
        _audit_unavailable(actor)
        raise VaultSensitiveAuthorizationRequired("Sensitive vault operation is unavailable")


def _critical_audit(**event):
    try:
        return record_critical_event(**event)
    except Exception as exc:
        raise VaultServiceUnavailable("Vault operation could not be completed") from exc


def _text(value, *, field, max_characters, required=True, max_utf8_bytes=None):
    if not isinstance(value, str):
        raise ValidationError({field: "Must be a string"})
    if required and not value:
        raise ValidationError({field: "Must not be blank"})
    if len(value) > max_characters or (max_utf8_bytes is not None and len(value.encode("utf-8")) > max_utf8_bytes):
        raise ValidationError({field: "Value is too long"})
    if _CONTROL_CHARACTERS.search(value):
        raise ValidationError({field: "Contains unsupported control characters"})
    return value


def _metadata(*, credential_type, label, service_label="", origin=""):
    allowed = {choice.value for choice in VaultRecord.CredentialType}
    if credential_type not in allowed:
        raise ValidationError({"credential_type": "Unsupported credential type"})
    metadata_contracts = {
        VaultRecord.CredentialType.LOGIN: {"service_label", "origin"},
        VaultRecord.CredentialType.API_TOKEN: {"service_label"},
        VaultRecord.CredentialType.SSH_KEY: set(),
        VaultRecord.CredentialType.GENERIC_SECRET: set(),
    }
    permitted = metadata_contracts[credential_type]
    if service_label and "service_label" not in permitted:
        raise ValidationError({"service_label": "Field is not available for this credential type"})
    if origin and "origin" not in permitted:
        raise ValidationError({"origin": "Field is not available for this credential type"})
    normalized_origin = ""
    if origin:
        origin = _text(origin, field="origin", max_characters=2048)
        parsed = urlsplit(origin)
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValidationError({"origin": "Must be a canonical HTTPS origin"}) from exc
        if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValidationError({"origin": "Must be a canonical HTTPS origin"})
        host = parsed.hostname.lower()
        normalized_origin = f"https://{host}" + (f":{port}" if port and port != 443 else "")
    return {
        "credential_type": credential_type,
        "label": _text(label, field="label", max_characters=120),
        "service_label": _text(service_label, field="service_label", max_characters=120, required=False),
        "origin": normalized_origin,
    }


def _encrypted_payload(credential_type, payload, *, require_secret=True):
    if not isinstance(payload, dict):
        raise ValidationError({"secret": "Encrypted fields must be an object"})
    contracts = {
        VaultRecord.CredentialType.LOGIN: ({"username", "password", "notes"}, {"password"}),
        VaultRecord.CredentialType.API_TOKEN: ({"token", "token_identifier", "notes"}, {"token"}),
        VaultRecord.CredentialType.SSH_KEY: ({"private_key", "passphrase", "notes"}, {"private_key"}),
        VaultRecord.CredentialType.GENERIC_SECRET: ({"secret", "account_identifier", "notes"}, {"secret"}),
    }
    allowed, required = contracts[credential_type]
    if set(payload) - allowed or (require_secret and not required.issubset(payload)):
        raise ValidationError({"secret": "Encrypted fields do not match credential type"})
    result = {}
    for name in sorted(allowed):
        if name not in payload:
            continue
        byte_limit = 64 * 1024 if name == "private_key" else 8 * 1024 if name == "notes" else 32 * 1024
        char_limit = 320 if name in {"username", "token_identifier", "account_identifier"} else byte_limit
        result[name] = _text(
            payload[name],
            field=name,
            max_characters=char_limit,
            required=name in required,
            max_utf8_bytes=byte_limit,
        )
    return result


def metadata_payload(record):
    return {
        "id": str(record.pk),
        "credential_type": record.credential_type,
        "label": record.label,
        "service_label": record.service_label,
        "origin": record.origin,
        "revision": record.revision,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def _encode_cursor(record):
    value = json.dumps({"created_at": record.created_at.isoformat(), "id": str(record.pk)}, separators=(",", ":"))
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_cursor(value):
    if not isinstance(value, str) or not value or len(value) > 256:
        raise ValidationError({"cursor": "Cursor is invalid"})
    try:
        raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        data = json.loads(raw.decode("utf-8"))
        created_at = datetime.fromisoformat(data["created_at"])
        record_id = uuid.UUID(data["id"])
    except (ValueError, TypeError, KeyError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError({"cursor": "Cursor is invalid"}) from exc
    if created_at.tzinfo is None or set(data) != {"created_at", "id"}:
        raise ValidationError({"cursor": "Cursor is invalid"})
    return created_at, record_id


def list_credentials(*, actor, credential_type=None, prefix=None, cursor=None, limit=25):
    fresh = _active_actor(actor)
    if fresh is None:
        raise VaultUnavailableError("Vault is unavailable")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValidationError({"limit": "Must be between 1 and 100"})
    queryset = VaultRecord.objects.filter(owner=fresh, lifecycle=VaultRecord.Lifecycle.ACTIVE)
    if credential_type is not None:
        if credential_type not in {choice.value for choice in VaultRecord.CredentialType}:
            raise ValidationError({"credential_type": "Unsupported credential type"})
        queryset = queryset.filter(credential_type=credential_type)
    if prefix is not None:
        prefix = _text(prefix, field="prefix", max_characters=120)
        queryset = queryset.filter(Q(label__startswith=prefix) | Q(service_label__startswith=prefix))
    if cursor is not None:
        created_at, record_id = _decode_cursor(cursor)
        queryset = queryset.filter(Q(created_at__lt=created_at) | Q(created_at=created_at, id__lt=record_id))
    records = list(queryset[: limit + 1])
    next_cursor = _encode_cursor(records[limit - 1]) if len(records) > limit else None
    return CredentialPage(records=records[:limit], next_cursor=next_cursor)


def get_credential_metadata(*, actor, record_id):
    fresh = _active_actor(actor)
    try:
        record = VaultRecord.objects.filter(pk=record_id, owner=fresh, lifecycle=VaultRecord.Lifecycle.ACTIVE).first()
    except (ValidationError, ValueError, TypeError):
        record = None
    if fresh is None or record is None:
        _audit_unavailable(actor)
        raise VaultUnavailableError("Credential is unavailable")
    return record


def _owner_key(owner):
    key_row = VaultOwnerKey.objects.select_for_update().filter(owner=owner, active_slot=True).first()
    kek = load_kek()
    if key_row is None:
        dek = os.urandom(DEK_BYTES)
        wrapped = wrap_dek(kek=kek, dek=dek, owner_id=owner.pk, key_version=1)
        key_row = VaultOwnerKey.objects.create(
            owner=owner,
            key_version=wrapped.key_version,
            envelope_version=wrapped.envelope_version,
            nonce=wrapped.nonce,
            wrapped_dek=wrapped.wrapped_dek,
            tag=wrapped.tag,
        )
        return key_row, dek
    envelope = WrappedKeyEnvelope(
        envelope_version=key_row.envelope_version,
        key_version=key_row.key_version,
        nonce=bytes(key_row.nonce),
        wrapped_dek=bytes(key_row.wrapped_dek),
        tag=bytes(key_row.tag),
    )
    return key_row, unwrap_dek(kek=kek, envelope=envelope, owner_id=owner.pk)


def _unwrap_key_row(owner, key_row):
    if key_row is None:
        raise VaultCryptoError("Vault key material is unavailable")
    envelope = WrappedKeyEnvelope(
        envelope_version=key_row.envelope_version,
        key_version=key_row.key_version,
        nonce=bytes(key_row.nonce),
        wrapped_dek=bytes(key_row.wrapped_dek),
        tag=bytes(key_row.tag),
    )
    return unwrap_dek(kek=load_kek(), envelope=envelope, owner_id=owner.pk)


def _key_by_version(key_rows, key_version):
    return next((row for row in key_rows if row.key_version == key_version), None)


def _context(record):
    return EncryptionContext(
        owner_id=record.owner_id,
        record_id=str(record.pk),
        credential_type=record.credential_type,
        schema_version=record.schema_version,
    )


def _record_envelope(record):
    return EncryptionEnvelope(
        envelope_version=record.envelope_version,
        schema_version=record.schema_version,
        key_version=record.key_version,
        nonce=bytes(record.nonce),
        ciphertext=bytes(record.ciphertext),
        tag=bytes(record.tag),
    )


def _encrypt_payload(record, payload, dek, key_version):
    plaintext = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return encrypt(dek=dek, plaintext=plaintext, context=_context(record), key_version=key_version)


def _decrypt_payload(record, dek):
    plaintext = decrypt(dek=dek, envelope=_record_envelope(record), context=_context(record))
    try:
        payload = json.loads(plaintext.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError, TypeError) as exc:
        raise VaultCryptoError("Vault plaintext is invalid") from exc
    if not isinstance(payload, dict):
        raise VaultCryptoError("Vault plaintext is invalid")
    return payload


def create_credential(*, actor, authorization, credential_type, label, secret_fields, service_label="", origin=""):
    _require_sensitive(actor, authorization)
    metadata = _metadata(credential_type=credential_type, label=label, service_label=service_label, origin=origin)
    payload = _encrypted_payload(credential_type, secret_fields)
    try:
        with transaction.atomic():
            owner = _active_actor(actor, lock=True)
            if owner is None:
                raise VaultUnavailableError("Vault is unavailable")
            if VaultRecord.objects.filter(owner=owner).count() >= MAX_RECORDS_PER_OWNER:
                raise VaultConflictError("Vault record limit reached")
            key_row, dek = _owner_key(owner)
            record = VaultRecord(id=uuid.uuid4(), owner=owner, key_version=key_row.key_version, nonce=b"0" * 12, ciphertext=b"0", tag=b"0" * 16, **metadata)
            envelope = _encrypt_payload(record, payload, dek, key_row.key_version)
            record.nonce, record.ciphertext, record.tag = envelope.nonce, envelope.ciphertext, envelope.tag
            record.save(force_insert=True)
            _critical_audit(
                action=SecurityAuditEvent.Action.VAULT_CREATED,
                actor_user_id=owner.pk,
                target_type=SecurityAuditEvent.TargetType.VAULT_RECORD,
                target_id=str(record.pk),
                outcome=SecurityAuditEvent.Outcome.SUCCESS,
            )
            return record
    except (VaultCryptoError, DatabaseError) as exc:
        raise VaultServiceUnavailable("Vault operation could not be completed") from exc


def _locked_record(actor, record_id, *, include_deleted=False, lock_owner_keys=False):
    owner = _active_actor(actor, lock=True)
    if owner is None:
        raise VaultUnavailableError("Credential is unavailable")
    key_rows = []
    if lock_owner_keys:
        key_rows = list(VaultOwnerKey.objects.select_for_update().filter(owner=owner).order_by("key_version"))
    queryset = VaultRecord.objects.select_for_update().filter(pk=record_id, owner=owner)
    if not include_deleted:
        queryset = queryset.filter(lifecycle=VaultRecord.Lifecycle.ACTIVE)
    try:
        record = queryset.first()
    except (ValidationError, ValueError, TypeError):
        record = None
    if record is None:
        raise VaultUnavailableError("Credential is unavailable")
    return owner, key_rows, record


def update_credential(*, actor, authorization, record_id, expected_revision, metadata_changes=None, secret_fields=None):
    _require_sensitive(actor, authorization)
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision <= 0:
        raise ValidationError({"expected_revision": "Must be a positive integer"})
    if not metadata_changes and secret_fields is None:
        raise ValidationError("At least one field is required")
    try:
        with transaction.atomic():
            owner, key_rows, record = _locked_record(actor, record_id, lock_owner_keys=secret_fields is not None)
            if record.revision != expected_revision:
                raise VaultConflictError("Credential was modified by another request")
            fields = []
            if metadata_changes:
                if set(metadata_changes) - {"label", "service_label", "origin"}:
                    raise ValidationError("Unsupported metadata field")
                metadata = _metadata(
                    credential_type=record.credential_type,
                    label=metadata_changes.get("label", record.label),
                    service_label=metadata_changes.get("service_label", record.service_label),
                    origin=metadata_changes.get("origin", record.origin),
                )
                for name in ("label", "service_label", "origin"):
                    if getattr(record, name) != metadata[name]:
                        setattr(record, name, metadata[name]); fields.append(name)
            if secret_fields is not None:
                changes = _encrypted_payload(record.credential_type, secret_fields, require_secret=False)
                if not changes:
                    raise ValidationError("At least one encrypted field must change")
                existing_dek = _unwrap_key_row(owner, _key_by_version(key_rows, record.key_version))
                payload = _decrypt_payload(record, existing_dek)
                payload.update(changes)
                payload = _encrypted_payload(record.credential_type, payload)
                key_row = next((row for row in key_rows if row.active_slot is True), None)
                dek = _unwrap_key_row(owner, key_row)
                envelope = _encrypt_payload(record, payload, dek, key_row.key_version)
                record.key_version, record.nonce, record.ciphertext, record.tag = key_row.key_version, envelope.nonce, envelope.ciphertext, envelope.tag
                fields.extend(("key_version", "nonce", "ciphertext", "tag"))
            if not fields:
                raise ValidationError("At least one field must change")
            record.revision += 1
            record.save(update_fields=(*dict.fromkeys(fields), "revision", "updated_at"))
            _critical_audit(
                action=SecurityAuditEvent.Action.VAULT_UPDATED,
                actor_user_id=owner.pk,
                target_type=SecurityAuditEvent.TargetType.VAULT_RECORD,
                target_id=str(record.pk),
                outcome=SecurityAuditEvent.Outcome.SUCCESS,
            )
            return record
    except (VaultCryptoError, DatabaseError) as exc:
        raise VaultServiceUnavailable("Vault operation could not be completed") from exc


def reveal_credential(*, actor, authorization, record_id):
    _require_sensitive(actor, authorization)
    deferred = None
    try:
        with transaction.atomic():
            owner, key_rows, record = _locked_record(actor, record_id, lock_owner_keys=True)
            dek = _unwrap_key_row(owner, _key_by_version(key_rows, record.key_version))
            deferred = DeferredReveal(_decrypt_payload(record, dek))
            _critical_audit(
                action=SecurityAuditEvent.Action.VAULT_REVEALED,
                actor_user_id=owner.pk,
                target_type=SecurityAuditEvent.TargetType.VAULT_RECORD,
                target_id=str(record.pk),
                outcome=SecurityAuditEvent.Outcome.SUCCESS,
            )
            transaction.on_commit(deferred._mark_committed)
        return deferred
    except (VaultCryptoError, DatabaseError) as exc:
        if deferred is not None:
            deferred.discard()
        raise VaultServiceUnavailable("Vault operation could not be completed") from exc


def delete_credential(*, actor, authorization, record_id, expected_revision):
    _require_sensitive(actor, authorization)
    try:
        with transaction.atomic():
            owner, _key_rows, record = _locked_record(actor, record_id)
            if record.revision != expected_revision:
                raise VaultConflictError("Credential was modified by another request")
            now = timezone.now()
            record.lifecycle = VaultRecord.Lifecycle.DELETED
            record.deleted_at = now
            record.restore_expires_at = now + timedelta(days=RESTORE_WINDOW_DAYS)
            record.revision += 1
            record.save(update_fields=("lifecycle", "deleted_at", "restore_expires_at", "revision", "updated_at"))
            _critical_audit(action=SecurityAuditEvent.Action.VAULT_DELETED, actor_user_id=owner.pk,
                target_type=SecurityAuditEvent.TargetType.VAULT_RECORD, target_id=str(record.pk), outcome=SecurityAuditEvent.Outcome.SUCCESS)
            return record
    except DatabaseError as exc:
        raise VaultServiceUnavailable("Vault operation could not be completed") from exc


def restore_credential(*, actor, authorization, record_id, expected_revision):
    _require_sensitive(actor, authorization)
    try:
        with transaction.atomic():
            owner, _key_rows, record = _locked_record(actor, record_id, include_deleted=True)
            if record.revision != expected_revision or record.lifecycle != VaultRecord.Lifecycle.DELETED:
                raise VaultConflictError("Credential cannot be restored")
            if record.restore_expires_at is None or record.restore_expires_at <= timezone.now():
                raise VaultConflictError("Credential cannot be restored")
            record.lifecycle = VaultRecord.Lifecycle.ACTIVE
            record.deleted_at = None
            record.restore_expires_at = None
            record.revision += 1
            record.save(update_fields=("lifecycle", "deleted_at", "restore_expires_at", "revision", "updated_at"))
            _critical_audit(action=SecurityAuditEvent.Action.VAULT_RESTORED, actor_user_id=owner.pk,
                target_type=SecurityAuditEvent.TargetType.VAULT_RECORD, target_id=str(record.pk), outcome=SecurityAuditEvent.Outcome.SUCCESS)
            return record
    except DatabaseError as exc:
        raise VaultServiceUnavailable("Vault operation could not be completed") from exc
