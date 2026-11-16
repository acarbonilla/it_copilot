# IC-023-T02C-1 — Controlled credential purge

**Status:** PASS WITH ACCEPTED LIMITATIONS; T02C-3 EXECUTION GATE CLOSED

**Specification:** IC-023-T02C-1-SPEC-v1.0

**Baseline:** `5ba0caddedbc73a11a42043b3839c96f16099095`

**Branch:** `feature/ic-023-controlled-purge`

**Governance:** TTDM Core Operational Standard, approved November 15, 2026

**Risk:** L3 — security-critical

**Product Owner status:** T02C-1 is accepted as PASS WITH ACCEPTED LIMITATIONS. Selective staging, commit, non-force push, and PR creation for the inspected T02C-1 paths are authorized under IC-023-T02C-1-GIT-01. PR merge and operational destructive purge are not authorized. Genuine T02C-3 backup qualification remains a mandatory hold.

## Authoritative P01/P02 specification

This section records IC-023-T02C-1-SPEC-v1.0 completely. The objective is a bounded, independently authorized, transactionally controlled `ACTIVE → DELETED → PURGED` terminal transition. Restore is allowed only while `now < restore_expires_at`; purge time eligibility begins at `now >= restore_expires_at`. Retention expiration alone never authorizes purge. A purged row retains the approved nonsecret tombstone and removes credential metadata and envelope material under the existing database constraints. IC-021, IC-022, and T02A contracts remain authoritative.

### P01-01 — Immutable candidate selection

1. A batch contains 1–100 unique records.
2. Each candidate binds credential UUID, owner identity, and positive expected revision.
3. Candidates are canonicalized deterministically.
4. The candidate set is cryptographically bound to an operation parameter digest.
5. The digest binds operation type, candidate identities/revisions, dry-run reference, backup checkpoint reference, application/schema contract versions, and relevant execution parameters.
6. Membership and revisions are immutable after preparation.
7. Implicit expansion, substitution, and partial execution are prohibited.
8. Any mismatch invalidates execution.

Acceptance: a changed candidate set cannot reuse a prepared authorization.

### P01-02 — Assessment and execution separation

1. A completed read-only assessment is mandatory.
2. It binds the same immutable candidates and revisions.
3. Execution explicitly references it.
4. Completion, parameters, identities, and revisions must match.
5. Execution independently revalidates authoritative database state.
6. Assessment never overrides later holds, revisions, retention, journals, or backup invalidation.
7. Stale/mismatched assessment requires new assessment and authorization.
8. Assessment never transitions a credential to `PURGED`.

Acceptance: neither a completed dry run nor eligible count independently authorizes destruction.

### P01-03 — Independent maintenance authorization

1. Execution requires an authenticated principal with `credential.purge`.
2. T02A protected-file maintenance authorization remains authoritative.
3. Missing, malformed, tampered, expired, disabled, or insufficient credentials fail closed.
4. Web session, ownership, App Admin, staff, and superuser status grant no maintenance authority.
5. Maintenance authentication is browser-independent.
6. Operator tokens never appear in CLI arguments, logs, audits, errors, or output.
7. Authorization is evaluated for the particular operation.

Acceptance: an App Admin without maintenance capability cannot purge.

### P01-04 — One-use execution confirmation

1. Execution requires a separate `VaultMaintenanceConfirmation`.
2. It binds exact execution operation and parameter digest.
3. It has explicit expiry.
4. It is valid only unused and unexpired.
5. Issuance requires an independently authenticated maintenance principal, never a Boolean flag.
6. Confirmation material never appears in arguments, logs, audit payloads, or persisted plaintext.
7. It is validated against the exact execution.
8. Consumption and lifecycle mutation are transactionally consistent.
9. Completed operations and consumed confirmations cannot authorize another attempt.
10. Failure/rollback cannot commit a partial purge.

Acceptance: expired, mismatched, consumed, or unrelated confirmation denies purge.

### P01-05 — Atomicity and deterministic locking

1. A batch runs in one database transaction.
2. Maximum batch size is 100.
3. Lock order is global guard, ordered owners, operation/journal/confirmation, holds, backup inventory, owner keys, and ordered records.
4. Ordering remains consistent with T02A.
5. Eligibility is revalidated after locks.
6. Any failed candidate rejects the batch.
7. Partial success is prohibited.
8. Tombstones, confirmation consumption, operation completion, and critical audit commit consistently.
9. Concurrency cannot duplicate execution.
10. No automatic destructive retry occurs without fresh authorization-state validation.

Acceptance: candidate or audit failure rolls back the entire batch.

### P01-06 — Mandatory per-candidate eligibility

Every candidate must be `DELETED`; have a restoration deadline with server time at/after it; match its expected revision; have no owner or record hold; have no conflicting unfinished journal; reference a completed matching dry run; have operation-specific qualified backup evidence; execute under `credential.purge`; have a matched unused unexpired confirmation; and be covered by required locks. Any failure denies the entire batch.

Acceptance: retention, hold, revision, journal, backup, authorization, confirmation, and locking gates cannot be bypassed.

### P01-07 — Terminal PURGED transition

Success transitions every candidate from `DELETED` to `PURGED`; retains approved nonsecret identity/lifecycle fields, purge timestamp, and opaque operation UUID; removes label, service label, origin, ciphertext, nonce, tag, and secret-bearing envelope/version fields; preserves revision/database invariants; writes operation-linked secret-free critical audit evidence; makes records unavailable to restore/reveal/edit; and retains tombstones under separately approved retention. It does not claim media sanitization, cryptographic destruction, or erasure from logs/snapshots/backups.

Acceptance: the tombstone satisfies existing constraints and cannot return to an active lifecycle.

### P01-08 — Replay, interruption, and recovery safety

Completed operations never execute twice; concurrent attempts have at most one success; stale candidates/revisions, expired/consumed confirmations, and unfinished conflicting journals deny execution; ambiguous/interrupted states fail closed; recovery requires separately verified transition; automatic destructive replay is prohibited; failed transactions do not partially purge; and verified completion is distinguishable from interruption.

Acceptance: crash, retry, concurrency, and replay cannot produce duplicate or partial destruction.

### P02-01 — Operation-specific qualified backup evidence

`VaultBackupSet.state == VERIFIED` is insufficient. The gate must derive authoritative evidence that the checkpoint is authentic, operation-bound, covers exact candidates/owners, matches application/database schema versions, covers encrypted data and recovery dependencies, provides protected/verifiable key recovery, satisfies manifest/bundle verification, has complete attributable recovery evidence, and is current/not invalidated. Unrelated, incomplete, stale, or unverified backup cannot qualify.

### P02-02 — No synthetic backup qualification

Manual `VERIFIED` state, arbitrary digest/inventory rows, environment bypasses, and Boolean success flags cannot qualify evidence. Fixtures cannot create a production-accessible bypass. Test doubles are limited to isolated negative/orchestration testing. Production execution requires genuine qualification. Qualification failure changes no lifecycle state.

### P02-03 — T02C-3 dependency

T02C-3 owns snapshot selection, authenticated manifests, protected key-recovery bundles, inventory reconciliation, recovery verification, and qualification. T02C-1 defines a strict proof interface that fails closed until T02C-3 exists and is verified. T02C-1 cannot invent an alternate producer/evidence path or weaken P02.

### P02-04 — Operational restriction

Operational purge of real data remains prohibited. Dry run, operator capability, syntactically valid confirmation, and generic `VERIFIED` inventory never remove the restriction. Positive qualification depends on genuine T02C-3 evidence. Until then operational execution fails closed and missing end-to-end qualification is `NOT VERIFIED`, never `PASS`.

## Minimum verification contract

Verification covers retention boundaries; invalid/expired/unauthorized principals and missing capability; owner/record holds; stale revisions; altered/duplicate candidates; dry-run mismatches; missing/generic/stale/mismatched/fabricated backup evidence; confirmation failures; conflicting journals; restore/purge and duplicate-execution concurrency; atomic rollback; interruption/restart; tombstone constraints; audit consistency; secret-free diagnostics; vault regressions; native MySQL concurrency; Django checks; and migration drift. Genuine positive end-to-end execution remains **NOT VERIFIED** until T02C-3 qualification exists. Evidence is classified CURRENT, REUSED, STALE, or MISSING.

## Explicit exclusions

No operational purge, KEK/DEK rotation, backup/recovery implementation, key retirement/destruction, HTTP maintenance endpoint, frontend maintenance control, infrastructure/deployment work, unrelated refactor, PR merge, or publication outside the inspected T02C-1 paths is authorized.

## Architecture and implementation record

### Candidate binding and assessment

`vault.purge.PurgeCandidate` is the strict `(credential UUID, owner ID, positive expected revision)` contract. `canonicalize_candidates()` rejects empty, duplicate, malformed, and over-100 sets and orders by owner then UUID. `purge_parameter_digest()` binds the canonical set, operation type, exact dry-run UUID, backup checkpoint UUID, maximum batch size, application version, and `vault-controlled-purge-v1` schema contract through the accepted domain-separated maintenance digest.

`assess_purge_candidates()` creates a candidate-bound `DRY_RUN` operation, performs a metadata-only assessment, records exact eligible/blocked counts, writes the critical `vault.purge_assessed` audit atomically, and never changes credential lifecycle or opens an envelope. Assessment intentionally does not claim backup qualification.

### Confirmation and execution preparation

`prepare_purge_execution()` re-locks and validates the completed dry run and exact digest. It requires two separately authenticated, unexpired maintenance principals with `credential.purge`; the confirmer must differ from the intended executor. It creates a `PENDING` execution, one-use confirmation, and `PENDING` purge journal atomically. Migration `vault.0005` adds the controlled opaque `issued_by_operator_id` attribution and seeds the global maintenance guard. The confirmation stores only a random domain-separated digest, exact operation/digest binding, expiry, issuer ID, and consumption time—no token or confirmation plaintext.

### Transaction and locking model

`execute_purge()` performs no retry and uses one atomic transaction. It locks the singleton global guard, ordered owners, execution and dry-run operations, journal, confirmation, ordered active holds, referenced backup inventory, ordered owner keys, and ordered credential rows. It revalidates principal/operation identity, state, schema/application versions, dry-run/digest equality, candidate cardinality/ownership/revisions, retention, holds, journals, and confirmation before backup qualification. The transition code is all-or-nothing and would atomically clear approved metadata/envelope fields, increment revision, persist the tombstone operation/time, consume confirmation, complete journal/operation, and write one critical `vault.purge_executed` audit.

### Fail-closed T02C-3 qualification seam

`qualify_purge_backup()` is the sole qualification seam and unconditionally raises `BackupQualificationUnavailable` in T02C-1. It accepts no Boolean, environment switch, caller-supplied evidence object, test double, or generic inventory state. Consequently the terminal-transition block is unreachable operationally in this checkpoint. A manually created `VERIFIED` `VaultBackupSet` is explicitly tested and cannot change lifecycle, consume confirmation, complete the operation, or emit execution audit. No command, HTTP route, frontend control, or alternate producer was added.

Genuine positive destructive execution, successful duplicate-execution serialization, restore-versus-purge winner behavior, audit-failure rollback after a qualified transition, and interruption after qualification remain **NOT VERIFIED** pending genuine T02C-3 recovery evidence. The code does not claim sanitization or destruction from media, logs, snapshots, or backups.

## Files and migration

- `apps/api/vault/purge.py` — candidate/digest, assessment, preparation, deterministic locks, strict qualification seam, and unreachable-until-qualified tombstone transaction.
- `apps/api/vault/models.py` — confirmation issuer attribution.
- `apps/api/vault/migrations/0005_vaultmaintenanceconfirmation_issued_by_operator_id.py` — additive field plus guard seed.
- `apps/api/vault/apps.py` and `apps/api/vault/signals.py` — idempotent post-migration restoration of the singleton maintenance guard after database/test flushes.
- `apps/api/vault/maintenance_services.py` — hold create/release now follow global guard → owner → hold ordering so a hold cannot race into the purge eligibility window.
- `apps/api/vault/tests/test_controlled_purge.py` — negative/orchestration and MySQL concurrency boundary tests using disposable rows only.
- This living record.

No backend HTTP route, frontend path, deployment, infrastructure, rotation, recovery, or operational-data action was added.

## Verification evidence

Environment: Windows, Python 3.13.5, Django 5.2.x, SQLite supplementary database. Commands were run from `apps/api` unless stated otherwise.

- **CURRENT:** `python manage.py test vault.tests.test_controlled_purge --settings=config.settings.test -v 1` — 12 discovered; 11 passed and the native-MySQL concurrency test skipped on SQLite.
- **CURRENT (GIT-01 pre-publication rerun):** `python manage.py test vault.tests.test_controlled_purge vault.tests.test_maintenance_foundations --settings=config.settings.test -v 1` — 24 run; 22 passed, 2 platform/native skips, no failures.
- **CURRENT (GIT-01 pre-publication rerun):** `python manage.py test vault --settings=config.settings.test -v 1` — 100 run; 88 passed, 12 native/environment skips, no failures.
- **REUSED:** Pre-hardening combined `python manage.py test vault session_auth accounts security_audit --settings=config.settings.test -v 1` — 213 run; 183 passed, 30 native/environment skips, no failures. Final changes were confined to vault locking/guard setup and are covered by the later final 100-test vault run; this combined total is not represented as final exact-tree evidence.
- **CURRENT:** disposable SQLite migration verification — full forward apply, rollback of `vault.0005`, forward reapply, and `migrate --check` passed; disposable database removed.
- **CURRENT (GIT-01 pre-publication rerun):** `python manage.py makemigrations --check --dry-run --settings=config.settings.test` — no drift.
- **CURRENT (GIT-01 pre-publication rerun):** `python manage.py check --settings=config.settings.test` — no issues.
- **CURRENT:** `python -m compileall -q vault` — passed.
- **CURRENT:** `git diff --check` — passed.
- **CURRENT:** production route scan — no purge route in Django URL/view modules.
- **CURRENT:** focused source scan — no logging/printing/storage of operator tokens, confirmation material, candidate metadata, or credential plaintext. Test ciphertext values are disposable sentinels.
- **CURRENT (GIT-01 pre-publication rerun):** Native MySQL concurrency invocation with credentials loaded from the protected repository `.env`: `python manage.py test vault.tests.test_controlled_purge.ControlledPurgeMySQLConcurrencyTests --settings=config.settings.local -v 1 --noinput` — the disposable `test_my_database` was created, all migrations through `vault.0005` applied, 1 test passed, and the test database was destroyed. No operational database row was changed and no purge qualified.
- **MISSING / NOT VERIFIED:** Genuine operation-matched backup qualification and every positive destructive-path result, by mandatory T02C-3 dependency.
- **REUSED:** Existing T02A tombstone database constraints and owner-facing unavailability regressions remain covered by the affected vault suite.
- **STALE:** No pre-T02C-1 test total is used as completion evidence.

The initial focused run exposed the missing singleton maintenance-guard seed and was not counted as a pass. A later test-only expiry setup attempted an impossible database state and was corrected to advance controlled server time; that failed setup run is also not represented as passing evidence.

## Security status and limitations

- Operational purge is unavailable and fails closed at the qualification seam even when candidates, dry run, operator, confirmation, and a generic `VERIFIED` inventory are otherwise valid.
- Positive execution tests deliberately do not patch, monkeypatch, instantiate, or bypass qualification.
- No operational or non-test credential was accessed or changed.
- Native MySQL duplicate-attempt locking evidence passed against a disposable test database; positive qualified-transition concurrency remains unavailable by the mandatory T02C-3 gate.
- T02C-3 must implement authenticated manifest/bundle recovery verification and an authoritative, operation-matched qualification result without adding a bypass flag or generic inventory shortcut.
- Confirmation issuer attribution is intentionally opaque and nonsecret; operator authentication remains protected-file based.
- Tombstone retention remains separately governed; no tombstone deletion exists.

## Repository publication and SOL handoff

IC-023-T02C-1-GIT-01 authorizes selective staging and commit of the inspected T02C-1 paths, non-force push of `feature/ic-023-controlled-purge`, and creation of an open PR targeting `main`. Merge remains separately gated and unauthorized. Operational destructive purge remains prohibited, positive qualified purge remains **NOT VERIFIED**, and genuine T02C-3 operation-matched backup qualification remains a mandatory hold.

Product Owner disposition: **PASS WITH ACCEPTED LIMITATIONS**. Publish for consolidated SOL review at T02D with a security status of **FAIL-CLOSED / OPERATIONAL EXECUTION NOT VERIFIED**. The PR must remain open and unmerged pending separate authorization.
