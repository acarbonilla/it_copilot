import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from .backup_contracts import BackupContractError, authenticate_manifest
from .backup_storage import validate_artifact, validate_protected_root
from .maintenance import _key, digest_parameters
from .models import VaultBackupSet


POLICY_VERSION = "vault-recovery-v1"
MAX_EVIDENCE_AGE = timedelta(hours=24)


class QualificationDenied(Exception):
    pass


@dataclass(frozen=True)
class PurgeBackupQualification:
    backup_set_id: str
    prepared_operation_id: str
    evidence_digest: str
    candidate_set_digest: str
    owner_set_digest: str


def candidate_set_digest(candidates):
    return digest_parameters({"candidates": [{
        "credentialId": str(item.credential_id), "ownerId": item.owner_id,
        "expectedRevision": item.expected_revision,
    } for item in candidates]})


def owner_set_digest(candidates):
    return digest_parameters({"ownerIds": sorted({item.owner_id for item in candidates})})


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def qualify_verified_backup(*, operation, backup_set, candidates, trusted_now=None):
    """Verify genuine artifact and recovery evidence. This does not enable operational purge."""
    now = trusted_now or timezone.now()
    try:
        evidence = backup_set.recovery_evidence
    except Exception:
        raise QualificationDenied("Backup qualification denied") from None
    if (backup_set.state != VaultBackupSet.State.VERIFIED or backup_set.verified_at is None or
            evidence.invalidated_at is not None or evidence.failure_code is not None or not evidence.cleanup_complete or
            evidence.verification_policy_version != POLICY_VERSION or evidence.expires_at <= now or
            now - evidence.verified_at > MAX_EVIDENCE_AGE or
            str(evidence.prepared_operation_id) != str(operation.pk) or
            str(evidence.dry_run_id) != str(operation.parent_dry_run_id) or
            evidence.parameter_digest != operation.parameter_digest or
            evidence.backup_operator_id == evidence.verifier_operator_id or
            evidence.candidate_set_digest != candidate_set_digest(candidates) or
            evidence.owner_set_digest != owner_set_digest(candidates)):
        raise QualificationDenied("Backup qualification denied")
    try:
        manifest_root = validate_protected_root(settings.VAULT_BACKUP_MANIFEST_ROOT)
        snapshot_root = validate_protected_root(settings.VAULT_BACKUP_SNAPSHOT_ROOT)
        bundle_root = validate_protected_root(settings.VAULT_BACKUP_BUNDLE_ROOT)
        manifest_path = validate_artifact(manifest_root / f"{backup_set.manifest_id}.json", root=manifest_root)
        snapshot_path = validate_artifact(snapshot_root / f"{backup_set.database_snapshot_id}.sql", root=snapshot_root)
        bundle_path = validate_artifact(bundle_root / f"{backup_set.protected_bundle_id}.bin", root=bundle_root)
        manifest_key = _key(settings.VAULT_MANIFEST_AUTH_KEY_FILE, setting_name="VAULT_MANIFEST_AUTH_KEY_FILE")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        unsigned = authenticate_manifest(manifest, key=manifest_key)
    except (OSError, UnicodeError, json.JSONDecodeError, BackupContractError, Exception) as exc:
        if isinstance(exc, QualificationDenied):
            raise
        raise QualificationDenied("Backup qualification denied") from None
    required_matches = (
        unsigned["backupSetId"] == str(backup_set.pk),
        unsigned["databaseSnapshotId"] == str(backup_set.database_snapshot_id),
        unsigned["protectedBundleId"] == str(backup_set.protected_bundle_id),
        unsigned["preparedOperationId"] == str(operation.pk),
        unsigned["dryRunId"] == str(operation.parent_dry_run_id),
        unsigned["purgeParameterDigest"] == operation.parameter_digest,
        unsigned["candidateSetDigest"] == evidence.candidate_set_digest,
        unsigned["ownerSetDigest"] == evidence.owner_set_digest,
        unsigned["databaseSnapshotDigest"] == _sha256(snapshot_path) == backup_set.snapshot_digest,
        unsigned["protectedBundleDigest"] == _sha256(bundle_path) == backup_set.bundle_digest,
        unsigned["applicationVersion"] == operation.application_version == backup_set.application_version,
        unsigned["schemaVersion"] == backup_set.schema_version,
    )
    if not all(required_matches):
        raise QualificationDenied("Backup qualification denied")
    return PurgeBackupQualification(str(backup_set.pk), str(operation.pk), evidence.evidence_digest,
                                    evidence.candidate_set_digest, evidence.owner_set_digest)
