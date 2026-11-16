import hashlib
import hmac
import json
import uuid
import secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from django.conf import settings

from .maintenance import MaintenanceAuthorizationDenied, _protected_file


MANIFEST_SCHEMA_VERSION = 2
BUNDLE_SCHEMA_VERSION = 2
MANIFEST_AUTH_ALGORITHM = "HMAC-SHA-256"
BUNDLE_ALGORITHM = "AES-256-GCM"


class BackupContractError(Exception):
    pass


MANIFEST_V2_FIELDS = frozenset({
    "manifestSchemaVersion", "manifestId", "backupSetId", "databaseSnapshotId", "snapshotMechanism",
    "toolVersion", "serverVersion", "snapshotSize", "databaseSnapshotDigest", "applicationVersion",
    "schemaVersion", "migrationFingerprint", "preparedOperationId", "dryRunId", "purgeParameterDigest",
    "candidateSetDigest", "ownerSetDigest", "candidateCount", "ownerCount", "snapshotEpoch",
    "snapshotStartedAt", "snapshotCompletedAt", "protectedBundleId", "bundleAlgorithm",
    "protectedBundleDigest", "protectedBundleSize", "keyInventoryDigest", "authenticationKeyId",
    "verificationPolicyVersion", "evidenceExpiresAt", "invalidationGeneration", "journalCheckpointId",
})


def canonical_manifest_bytes(manifest):
    if not isinstance(manifest, dict):
        raise BackupContractError("Backup manifest is invalid")
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def authenticate_manifest(manifest, *, key):
    if not isinstance(key, bytes) or len(key) < 32:
        raise BackupContractError("Manifest authentication key is invalid")
    unsigned = dict(manifest)
    supplied = unsigned.pop("authentication", None)
    version = unsigned.get("manifestSchemaVersion")
    legacy_required = {
        "manifestSchemaVersion", "backupSetId", "databaseSnapshotId", "databaseSnapshotDigest",
        "protectedBundleId", "protectedBundleDigest", "applicationVersion", "schemaVersion",
        "keyInventoryDigest", "journalCheckpointId", "retentionState", "holdSummary",
        "createdAt", "authenticationKeyId",
    }
    required = MANIFEST_V2_FIELDS if version == MANIFEST_SCHEMA_VERSION else legacy_required
    if set(unsigned) != required or version not in (1, MANIFEST_SCHEMA_VERSION):
        raise BackupContractError("Backup manifest is invalid")
    try:
        uuid.UUID(unsigned["backupSetId"])
        uuid.UUID(unsigned["databaseSnapshotId"])
        uuid.UUID(unsigned["protectedBundleId"])
    except (ValueError, TypeError, AttributeError):
        raise BackupContractError("Backup manifest is invalid") from None
    domain = b"vault-backup-manifest-v2\x00" if version == 2 else b"vault-backup-manifest-v1\x00"
    expected = hmac.new(key, domain + canonical_manifest_bytes(unsigned),
                        hashlib.sha256).hexdigest()
    if not isinstance(supplied, dict) or supplied.get("algorithm") != MANIFEST_AUTH_ALGORITHM or not hmac.compare_digest(
            str(supplied.get("mac", "")), expected):
        raise BackupContractError("Backup manifest authentication failed")
    return unsigned


def authenticate_manifest_v2(unsigned, *, key):
    if set(unsigned) != MANIFEST_V2_FIELDS or unsigned.get("manifestSchemaVersion") != 2:
        raise BackupContractError("Backup manifest is invalid")
    document = dict(unsigned)
    document["authentication"] = {
        "algorithm": MANIFEST_AUTH_ALGORITHM,
        "mac": hmac.new(key, b"vault-backup-manifest-v2\x00" + canonical_manifest_bytes(unsigned),
                        hashlib.sha256).hexdigest(),
    }
    authenticate_manifest(document, key=key)
    return document


def bundle_aad(*, backup_set_id, bundle_id, application_version, schema_version):
    value = {
        "applicationVersion": application_version,
        "backupSetId": str(uuid.UUID(str(backup_set_id))),
        "bundleId": str(uuid.UUID(str(bundle_id))),
        "bundleSchemaVersion": BUNDLE_SCHEMA_VERSION,
        "schemaVersion": schema_version,
    }
    return canonical_manifest_bytes(value)


def bundle_aad_v2(*, backup_set_id, bundle_id, manifest_id, snapshot_id, snapshot_digest,
                  application_version, schema_version, key_inventory_digest):
    return canonical_manifest_bytes({
        "applicationVersion": application_version,
        "backupSetId": str(uuid.UUID(str(backup_set_id))),
        "bundleContractVersion": BUNDLE_SCHEMA_VERSION,
        "bundleId": str(uuid.UUID(str(bundle_id))),
        "keyInventoryDigest": key_inventory_digest,
        "manifestId": str(uuid.UUID(str(manifest_id))),
        "schemaVersion": schema_version,
        "snapshotDigest": snapshot_digest,
        "snapshotId": str(uuid.UUID(str(snapshot_id))),
    })


def encrypt_key_bundle(payload, *, protection_key, aad):
    if not isinstance(protection_key, bytes) or len(protection_key) != 32:
        raise BackupContractError("Bundle protection key is invalid")
    if not isinstance(payload, dict) or set(payload) != {"bundleContractVersion", "keys"}:
        raise BackupContractError("Recovery bundle is invalid")
    versions = [item.get("version") for item in payload["keys"] if isinstance(item, dict)]
    if (payload["bundleContractVersion"] != BUNDLE_SCHEMA_VERSION or not versions or
            any(not isinstance(v, int) or v <= 0 for v in versions) or len(set(versions)) != len(versions)):
        raise BackupContractError("Recovery bundle is invalid")
    nonce = secrets.token_bytes(12)
    plaintext = canonical_manifest_bytes(payload)
    ciphertext = AESGCM(protection_key).encrypt(nonce, plaintext, aad)
    return nonce + ciphertext


def decrypt_key_bundle(blob, *, protection_key, aad):
    if not isinstance(protection_key, bytes) or len(protection_key) != 32 or not isinstance(blob, bytes) or len(blob) < 29:
        raise BackupContractError("Recovery bundle is invalid")
    try:
        payload = json.loads(AESGCM(protection_key).decrypt(blob[:12], blob[12:], aad).decode("utf-8"))
    except (InvalidTag, UnicodeError, json.JSONDecodeError):
        raise BackupContractError("Recovery bundle authentication failed") from None
    if not isinstance(payload, dict) or set(payload) != {"bundleContractVersion", "keys"}:
        raise BackupContractError("Recovery bundle is invalid")
    versions = [entry.get("version") for entry in payload["keys"] if isinstance(entry, dict)]
    if payload["bundleContractVersion"] != 2 or not versions or len(versions) != len(payload["keys"]) or len(set(versions)) != len(versions):
        raise BackupContractError("Recovery bundle is invalid")
    return payload


def validate_backup_configuration():
    repository = Path(settings.REPOSITORY_DIR).resolve()
    roots = []
    for name in ("VAULT_BACKUP_SNAPSHOT_ROOT", "VAULT_BACKUP_MANIFEST_ROOT", "VAULT_BACKUP_BUNDLE_ROOT"):
        value = getattr(settings, name, "")
        path = Path(value) if isinstance(value, str) and value else None
        if path is None or not path.is_absolute() or path.is_symlink():
            raise BackupContractError(f"{name} is invalid")
        resolved = path.resolve()
        if resolved == repository or repository in resolved.parents:
            raise BackupContractError(f"{name} is invalid")
        roots.append(resolved)
    if any(left == right or left in right.parents or right in left.parents
           for index, left in enumerate(roots) for right in roots[index + 1:]):
        raise BackupContractError("Backup roots must be separated")
    try:
        manifest_key = _protected_file(getattr(settings, "VAULT_MANIFEST_AUTH_KEY_FILE", ""),
                                       setting_name="VAULT_MANIFEST_AUTH_KEY_FILE")
        bundle_key = _protected_file(getattr(settings, "VAULT_BUNDLE_PROTECTION_KEY_FILE", ""),
                                     setting_name="VAULT_BUNDLE_PROTECTION_KEY_FILE")
    except MaintenanceAuthorizationDenied as exc:
        raise BackupContractError("Backup key configuration is invalid") from exc
    if manifest_key == bundle_key:
        raise BackupContractError("Backup protection keys must be distinct")
    return tuple(roots), manifest_key, bundle_key
