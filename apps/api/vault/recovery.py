import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from django.utils import timezone

from .backup_contracts import BackupContractError
from .maintenance import MaintenancePrincipal, digest_parameters


_DISPOSABLE_DATABASE = re.compile(r"^test_vault_recovery_[0-9a-f]{32}$")


class RecoveryVerificationError(Exception):
    pass


@dataclass(frozen=True)
class RecoveryVerificationResult:
    evidence_digest: str
    candidate_count: int
    owner_count: int
    key_count: int
    verified_at: object
    cleanup_complete: bool


def require_disposable_database(name):
    if not isinstance(name, str) or not _DISPOSABLE_DATABASE.fullmatch(name):
        raise RecoveryVerificationError("Recovery target is not disposable")
    return name


def restore_disposable_snapshot(*, principal, database_name, mysql_executable, defaults_file, snapshot_path,
                                timeout=1800):
    if (not isinstance(principal, MaintenancePrincipal) or "recovery.verify" not in principal.capabilities or
            principal.expires_at <= timezone.now()):
        raise RecoveryVerificationError("Recovery verification denied")
    require_disposable_database(database_name)
    snapshot = Path(snapshot_path)
    if not snapshot.is_file() or snapshot.is_symlink():
        raise RecoveryVerificationError("Recovery snapshot is invalid")
    command = [str(mysql_executable), f"--defaults-extra-file={defaults_file}", database_name]
    try:
        with snapshot.open("rb") as sql:
            result = subprocess.run(command, stdin=sql, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                    timeout=timeout, check=False,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        raise RecoveryVerificationError("Disposable recovery restore failed") from None
    if result.returncode:
        raise RecoveryVerificationError("Disposable recovery restore failed")


def recovery_evidence_digest(*, backup_set_id, operation_id, dry_run_id, parameter_digest,
                             candidate_digest, owner_digest, snapshot_digest, bundle_digest,
                             candidate_count, owner_count, key_count):
    return digest_parameters({
        "backupSetId": str(backup_set_id), "operationId": str(operation_id), "dryRunId": str(dry_run_id),
        "parameterDigest": parameter_digest, "candidateDigest": candidate_digest, "ownerDigest": owner_digest,
        "snapshotDigest": snapshot_digest, "bundleDigest": bundle_digest, "candidateCount": candidate_count,
        "ownerCount": owner_count, "keyCount": key_count, "policy": "vault-recovery-v1",
    })
