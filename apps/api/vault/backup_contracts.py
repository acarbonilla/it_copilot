import hashlib
import hmac
import json
import uuid
from pathlib import Path

from django.conf import settings

from .maintenance import MaintenanceAuthorizationDenied, _protected_file


MANIFEST_SCHEMA_VERSION = 1
BUNDLE_SCHEMA_VERSION = 1
MANIFEST_AUTH_ALGORITHM = "HMAC-SHA-256"
BUNDLE_ALGORITHM = "AES-256-GCM"


class BackupContractError(Exception):
    pass


def canonical_manifest_bytes(manifest):
    if not isinstance(manifest, dict):
        raise BackupContractError("Backup manifest is invalid")
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def authenticate_manifest(manifest, *, key):
    if not isinstance(key, bytes) or len(key) < 32:
        raise BackupContractError("Manifest authentication key is invalid")
    unsigned = dict(manifest)
    supplied = unsigned.pop("authentication", None)
    required = {
        "manifestSchemaVersion", "backupSetId", "databaseSnapshotId", "databaseSnapshotDigest",
        "protectedBundleId", "protectedBundleDigest", "applicationVersion", "schemaVersion",
        "keyInventoryDigest", "journalCheckpointId", "retentionState", "holdSummary",
        "createdAt", "authenticationKeyId",
    }
    if set(unsigned) != required or unsigned.get("manifestSchemaVersion") != MANIFEST_SCHEMA_VERSION:
        raise BackupContractError("Backup manifest is invalid")
    try:
        uuid.UUID(unsigned["backupSetId"])
        uuid.UUID(unsigned["databaseSnapshotId"])
        uuid.UUID(unsigned["protectedBundleId"])
    except (ValueError, TypeError, AttributeError):
        raise BackupContractError("Backup manifest is invalid") from None
    expected = hmac.new(key, b"vault-backup-manifest-v1\x00" + canonical_manifest_bytes(unsigned),
                        hashlib.sha256).hexdigest()
    if not isinstance(supplied, dict) or supplied.get("algorithm") != MANIFEST_AUTH_ALGORITHM or not hmac.compare_digest(
            str(supplied.get("mac", "")), expected):
        raise BackupContractError("Backup manifest authentication failed")
    return unsigned


def bundle_aad(*, backup_set_id, bundle_id, application_version, schema_version):
    value = {
        "applicationVersion": application_version,
        "backupSetId": str(uuid.UUID(str(backup_set_id))),
        "bundleId": str(uuid.UUID(str(bundle_id))),
        "bundleSchemaVersion": BUNDLE_SCHEMA_VERSION,
        "schemaVersion": schema_version,
    }
    return canonical_manifest_bytes(value)


def validate_backup_configuration():
    repository = Path(settings.REPOSITORY_DIR).resolve()
    roots = []
    for name in ("VAULT_BACKUP_MANIFEST_ROOT", "VAULT_BACKUP_BUNDLE_ROOT"):
        value = getattr(settings, name, "")
        path = Path(value) if isinstance(value, str) and value else None
        if path is None or not path.is_absolute() or path.is_symlink():
            raise BackupContractError(f"{name} is invalid")
        resolved = path.resolve()
        if resolved == repository or repository in resolved.parents:
            raise BackupContractError(f"{name} is invalid")
        roots.append(resolved)
    if roots[0] == roots[1] or roots[0] in roots[1].parents or roots[1] in roots[0].parents:
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
