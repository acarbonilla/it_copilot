# IC-023-T02C-3 — Controlled backup and recovery

**Task:** IC-023-T02C-3-T01
**Baseline:** `8ad8b52c07f07ec2dd5b4e2f545e1c7c3d412207`
**Branch:** `feature/ic-023-backup-recovery`
**Risk:** L3 — security-critical
**Status:** PASS WITH ACCEPTED LIMITATIONS
**Git publication:** AUTHORIZED BY IC-023-T02C-3-GIT-01; PR MERGE NOT AUTHORIZED
**Operational purge:** MANDATORY HOLD

## Authorization boundary

Product Owner authorization covers the accepted local implementation, focused tests, disposable MySQL backup/recovery verification, the four mandatory security remediations, living documentation, and publication under IC-023-T02C-3-GIT-01. It does not authorize PR merge, deployment, operational backup/recovery, operational purge, key rotation, key retirement, or destructive backup disposal.

## B01 — database snapshot

The primary architecture is version-qualified `mysqldump` using `--single-transaction`, `--quick`, `--hex-blob`, `--routines`, `--events`, `--triggers`, and `--set-gtid-purged=OFF`. The snapshot service requires an all-InnoDB schema, holds a server-enforced `FLUSH TABLES WITH READ LOCK` for the protected interval to exclude DDL and incompatible writes, uses a protected temporary client option file so credentials never enter command arguments, enforces the 1 GiB/30-minute ceilings, fsyncs output, streams SHA-256 calculation, and atomically publishes on the same volume. Failure and timeout remove only positively identified partial files.

MySQL Shell remains an approved architecture fallback but is **NOT IMPLEMENTED / NOT VERIFIED**. There is no automatic fallback.

## B02 — protected storage and ACL matrix

Three independent absolute roots are configured outside the repository: snapshot, manifest, and bundle. Root validation rejects missing/non-directory paths, repository containment, symlinks, Windows reparse points, broad principals (`Everyone`, `BUILTIN\Users`, `Authenticated Users`), missing required SIDs, and unavailable ACL inspection. On non-Windows systems, group/other access is rejected. Artifacts must be regular direct children of their validated root.

Portable code accepts configured SIDs and contains no personal SID. The approved matrix is:

| Identity | Snapshot | Manifest | Bundle | External keys |
|---|---:|---:|---:|---:|
| Backup service identity | write/read | write/read | write/read | read only as required |
| Recovery verifier | read | read | read | read manifest/bundle keys |
| Maintenance operator | no direct artifact access by default | read metadata only if approved | no direct access | no access |
| Ordinary users/broad groups | none | none | none | none |

Operational SID values and key custody remain deployment-specific and unconfigured.

## B03 — authenticated manifest v2

Manifest v2 is exact-field canonical UTF-8 JSON authenticated with domain-separated HMAC-SHA-256 and constant-time MAC comparison. It binds backup/snapshot/manifest/bundle IDs, mechanism and tool/server versions, sizes and digests, application and migration/schema versions, prepared operation and dry run, purge parameter digest, canonical candidate/owner digests and counts, epoch/timestamps, key inventory, verification policy, expiry, invalidation generation, and journal checkpoint. Authentication precedes use. Legacy v1 verification remains readable for accepted T02A tests but cannot qualify the v2 purge path.

## B04 — historical-key recovery bundle

Bundle v2 uses AES-256-GCM with a fresh 96-bit nonce. AAD binds backup, bundle, manifest and snapshot identities, snapshot digest, application/schema versions, key inventory digest, and contract version. Payload validation requires unique positive historical KEK versions. Wrong keys, AAD, tags, duplicate versions, malformed payloads, and missing key coverage fail closed. Bundle-protection, manifest-authentication, database, and maintenance credentials are excluded from the payload. Only disposable test keys are used by this checkpoint.

## B05 — disposable recovery

Recovery targets must match `test_vault_recovery_<32 lowercase hex>` and use a principal with `recovery.verify`. The restore runner accepts credentials only through an external defaults file, suppresses SQL output, reports controlled errors, and refuses an operational database name. Native verification creates a unique database, imports the snapshot, verifies restored table presence, and drops only that exact disposable database in `finally`. SQL import alone does not create recovery evidence; candidate/revision, key inventory, wrapped-DEK, envelope, holds, journals, cleanup, and authenticated artifact checks remain required by qualification.

## B06 — inventory and reconciliation

The accepted inventory state vocabulary remains `PREPARING → FILES_COMPLETE → REGISTERED → VERIFIED`, with `FAILED` and `RECONCILE`. `VaultRecoveryEvidence` records nonsecret exact-operation bindings, distinct backup/verifier identities, policy, evidence digest, 24-hour-or-shorter expiry, invalidation, and cleanup completion. Ambiguous/missing artifacts, failed cleanup, expiry, invalidation, operator collision, or digest mismatch cannot qualify. Retention is 90 days; holds override expiry; automatic disposal remains prohibited.

Full filesystem/database crash reconciliation orchestration is **MISSING / NOT VERIFIED**; the state and fail-closed checks are present.

## Accepted deferred requirements

- **D01:** MySQL Shell fallback is not implemented or verified.
- **D02:** Complete filesystem/database crash reconciliation is not implemented.
- **D03:** Operational key custody, Windows SID configuration, escrow, and recovery readiness require separate approval.
- **D04:** Successful operational purge execution, destructive-path concurrency, and rollback remain NOT VERIFIED.
- **D05:** Consolidated L3 independent review at T02D remains pending.

These accepted limitations do not establish B01-B08 operational readiness and do not authorize operational backup, recovery, or destructive purge.

## B07 — purge qualification

`qualify_verified_backup()` returns an immutable typed result only after recovery-evidence state, exact operation/dry-run/parameter/candidate/owner bindings, operator separation, currentness, manifest HMAC, artifact paths, snapshot/bundle hashes, and application/schema versions match. A generic `VERIFIED` row is insufficient.

`qualify_purge_backup()` invokes genuine verification and then unconditionally raises `OperationalPurgeDisabled`. This independent code boundary is not an environment flag, Boolean, fixture, or inventory state. No command or HTTP route enables purge. Disposable tests can validate the qualification engine without reaching the tombstone transition.

## B08 — operator separation

Existing protected-file authentication and capabilities remain authoritative. Backup creator, recovery verifier, purge confirmer, and purge executor identities are persisted and checked where applicable. Backup creator and recovery verifier must differ. App Admin, superuser, owner, browser session, and environment flags confer no maintenance authority.

## Mandatory remediation outcomes

- **REV01-F01:** caller-controlled `now` was removed from purge assessment/preparation/execution interfaces. A private trusted clock is captured at authorization boundaries, executor expiry is rechecked after the global/owner locks, and tests patch the private clock rather than passing production time.
- **REV01-F02:** execution rejects empty, `legacy-unattributed`, or same-as-executor confirmation issuers before qualification.
- **REV01-F03:** T02C-1 evidence wording now says concurrent fail-closed attempts only; successful serialization remains NOT VERIFIED.
- **P2 journal scope:** `VaultPurgeJournalScope` atomically persists each journal's exact owner/record/revision scope. Conflict queries include batch scope and treat unknown legacy purge journals as globally conflicting. Scope rows are protected from orphaning or silent deletion.

## Threat and failure analysis

Credentials are kept out of process arguments and controlled errors. Snapshot DDL consistency relies on a server-enforced global read lock, not a process mutex. Manifest tampering, artifact replacement, bundle authentication failure, historical-key gaps, stale evidence, operator collision, candidate mutation, cleanup ambiguity, and legacy confirmation/journal state fail closed. Artifact roots and external key files are separated. No claim is made for media sanitization, automatic disposal, operational key escrow, or operational recovery readiness.

## Verification evidence

- **CURRENT:** `python manage.py test vault.tests.test_controlled_purge vault.tests.test_backup_recovery vault.tests.test_maintenance_foundations --settings=config.settings.test -v 1` — 32 tests run, 29 passed, 3 skipped.
- **CURRENT:** `python manage.py test vault --settings=config.settings.test -v 1` — 108 tests run, 95 passed, 13 skipped.
- **CURRENT:** `python manage.py test accounts session_auth security_audit --settings=config.settings.test -v 1` — 113 tests run, 95 passed, 18 skipped.
- **CURRENT:** `python manage.py test vault.tests.test_backup_recovery.NativeMySQLBackupRecoveryTests vault.tests.test_controlled_purge.ControlledPurgeMySQLConcurrencyTests --settings=config.settings.local -v 2 --noinput` — 2 tests run and passed against the disposable Django MySQL test database. The recovery test created, restored, verified, and dropped only a unique `test_vault_recovery_<32 lowercase hex>` database.
- **CURRENT:** `python manage.py makemigrations --check --dry-run` — no model drift; `python manage.py check` — no issues; `git diff --check` — clean.
- **REUSED:** T02C-1 accepted full-vault and native fail-closed evidence at merge commit `8ad8b52c...`.
- **MISSING / NOT VERIFIED:** MySQL Shell fallback, successful operational purge serialization, operational key custody/escrow, full crash reconciliation, and T02D independent review.

## Repository state

Publication is authorized by IC-023-T02C-3-GIT-01 from `.worktrees/ic023c3`. The Product Owner decision is PASS WITH ACCEPTED LIMITATIONS. Operational destructive purge remains prohibited even when disposable qualification succeeds. PR merge requires separate explicit Product Owner authorization.
