# IC-028 Specification — READY Artifact Consistency and Critical Audit Rollback

**Status:** Implemented locally; SOL G2 review pending
**Baseline:** `fb946bfbcf5f9f6c61eda0f09cbbf3aebf0b768e`
**Feature status:** F-03 remains G2 HOLD; PR #22 is not authorized for merge.

## Problem and invariants

The processing-success transaction previously created an extracted reference, changed the version to `READY`, assigned `current_version`, cleared the candidate, and completed the job without a critical audit or authoritative validation of both physical artifacts. Recovery could also mark the current version failed without clearing the pointer.

The controlled publication boundary now requires an existing original reference and a proposed extracted artifact whose private regular files match their recorded byte lengths and SHA-256 digests. Neither key may have a quarantine tombstone. The active lease, active document, candidate relationship, extracted metadata, READY transition, current assignment, candidate clearing, job success, and `document.processing_succeeded` audit are validated or committed atomically.

Lock order remains: singleton artifact-publication guard, then document, version, and job rows. Compensation uses the same guard before reference checks. Filesystem availability is guaranteed only at the guarded validation point; ACLs, integrity-checked access, and reconciliation cover later degradation.

Terminal worker `FAILED` or `CANCELLED` transitions record `document.processing_failed` in the same transaction. Ordinary `RETRY_WAIT` transitions are not critically audited. Both system processing actions use a null system actor, the IT-document target type, the document UUID, and the controlled success/failure outcome; the audit schema has no free-form metadata field.

Ambiguous publication cleanup starts a fresh guarded transaction and preserves the physical file if either artifact table references it, if a tombstone exists, or if reference state cannot be established. Invalid-artifact reconciliation clears `current_version` only when it points to the failed version and never selects an older version automatically.

The historical assessment is read-only, uses signed 24-hour actor/root/physical-mode-bound cursors, scans keyset batches of at most 256 rows, and applies the existing 5,000-unit default/10,000 maximum budget. Database-reference checks are always performed. Optional physical checking stream-hashes artifacts of READY versions; it does not repair data or perform filesystem I/O in migrations.

## Acceptance criteria

1. READY requires valid original and proposed extracted artifacts at publication.
2. Both physical files must exist and match byte length and SHA-256.
3. Tombstoned original or extracted keys block publication.
4. Invalid artifacts cannot become current.
5. Success-audit failure rolls back the publication bundle.
6. Compensation never removes a referenced artifact after ambiguous outcomes.
7. Native MySQL concurrency preserves claim/publication/quarantine/reconciliation invariants.
8. Invalid-artifact recovery clears only the affected current pointer and audit failure rolls back.
9. Failure and retry remain idempotent and recoverable.
10. IC-026/IC-027 regressions, migrations, checks, and documentation pass.
11. Critical audit failures are surfaced and never reported as success.
12. Uncertain reference state causes fail-closed compensation.
13. Historical assessment is bounded, read-only, and accurately reports coverage.
