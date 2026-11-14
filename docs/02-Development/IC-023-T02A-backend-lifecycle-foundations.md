# IC-023-T02A — Backend lifecycle foundations

**Status:** IMPLEMENTED AND DEVELOPER-VERIFIED IN ISOLATED WORKTREE

**Authorized baseline:** `820c59a33f9fd399bbce439af51c406b09c97e8b`

**Branch:** `feature/ic-023-vault-lifecycle-foundations`

**Authority:** Product Owner execution authorization for IC-023-T02A only

## Scope and G1 authority

This checkpoint implements the approved IC-023 R03–R07, M01–M04, and B01–B04 foundations. It adds deleted-credential discovery, exact retention predicates, a terminal nonsecret tombstone shape, independent maintenance authorization, holds, accountable operation/journal/confirmation/backup inventory records, controlled audit vocabulary, and read-only command boundaries.

It does not implement frontend behavior, envelope purge, key rotation, snapshot or key-bundle creation, recovery, online retirement, cryptographic destruction, production-data maintenance, IC-024, deployment, or infrastructure.

## Deleted-credential API

`GET /api/v1/vault/deleted-credentials?limit=25&cursor=<opaque>`

- Requires an active authenticated owner; no application role grants another owner's access.
- Returns only `DELETED` records owned by the caller, in deterministic `-created_at, -id` order.
- Limit range is 1–100 and pagination uses an opaque bounded keyset cursor.
- The explicit response allowlist is `id`, `credential_type`, `label`, `service_label`, `origin`, `revision`, `restorationEligible`, and `restorationExpiresAt`.
- Eligibility is evaluated with timezone-aware server time. The exact boundary is `now < restore_expires_at`; equality is ineligible for restore and eligible by time for future purge assessment.
- Active and purged records, deletion timestamps, holds, journals, keys, envelope columns, and other owners are absent.
- Responses use `Cache-Control: no-store, private`, `Pragma: no-cache`, and `X-Content-Type-Options: nosniff`.

## Lifecycle and retention invariants

The schema supports `ACTIVE → DELETED → PURGED`, but T02A exposes no executable `PURGED` transition.

- `ACTIVE` has no lifecycle timestamps and retains complete metadata and envelope material.
- `DELETED` retains complete metadata/envelope material plus deletion and restoration-expiry timestamps.
- `PURGED` requires deletion, restoration-expiry, purge time, and opaque purge-operation UUID while requiring label, service label, origin, schema/envelope/key versions, nonce, ciphertext, and tag to be null.
- Active/deleted envelope lengths and versions remain constrained.
- Purged tombstones are excluded from the 1,000 active/deleted owner cap.
- Tombstones remain indefinitely pending a separate approved retention policy.
- Restoration clears deletion timestamps through the existing grant-protected service. A later deletion starts a new 30-day period.

The read-only purge predicate fails closed on retention, revision, active holds, conflicting journals, missing verified checkpoint, missing capability, missing completed dry run, and missing/invalid confirmation. It cannot mutate a credential.

## Maintenance authorization

Maintenance authorization is independent of App Admin, staff, superuser, IT role, ownership, and browser sessions. No HTTP maintenance route exists.

- `VAULT_MAINTENANCE_OPERATORS_FILE` is absolute, outside the repository, not a symlink, restrictively permissioned, schema-versioned, and protected by a domain-separated HMAC-SHA-256 file MAC.
- `VAULT_MAINTENANCE_AUTH_KEY_FILE` is a separate protected external key file.
- Operator IDs are opaque and each entry contains enabled state, explicit capability set, expiry, and a domain-separated token digest—never the raw token.
- Tokens are supplied through protected token files, never CLI arguments.
- Authorization is reloaded on every command invocation and uses constant-time digest comparisons.
- Missing, malformed, tampered, expired, disabled, underprivileged, unsafe, or repository-local files fail closed with a fixed denial.
- Capability vocabulary is `credential.purge`, `credential.hold.create`, `credential.hold.release`, `key.rotate.kek`, `key.rotate.dek`, `backup.create`, `recovery.verify`, and `key.retire.online`.

Windows ACL validation rejects broad `Everyone`, `BUILTIN\\Users`, and authenticated-user access and fails closed if ACL inspection cannot complete. Production-host ACL qualification remains an operational boundary.

## Holds, operations, confirmations, journals, and backup inventory

- `VaultMaintenanceOperation` stores only an opaque operator ID, controlled capability/mode/state, parameter digest, safe counts/cursor, version identifiers, timestamps, and controlled failure code.
- `VaultMaintenanceConfirmation` is one-use, operation-bound, parameter-bound, expiring metadata; T02A exposes no destructive consumer.
- `VaultMaintenanceHold` supports owner and record scopes, controlled reason codes, separate create/release operators and operations, and constrained active/released states.
- Hold create/release services require their exact capabilities and commit their controlled audit atomically. No browser route exists.
- `VaultMaintenanceJournal` represents purge/KEK rotation/DEK rotation/recovery state and safe checkpoint metadata without key material or plaintext. No key-changing implementation exists.
- `VaultBackupSet` represents PREPARING, FILES_COMPLETE, REGISTERED, VERIFIED, FAILED, and RECONCILE foundations. VERIFIED requires both a verification timestamp and evidence digest.

Future manifests use canonical UTF-8 JSON authenticated with HMAC-SHA-256. Future protected bundles use AES-256-GCM with fresh nonces and AAD binding backup-set, bundle, and application/schema identities. Manifest authentication and bundle-protection files must be distinct and outside the repository; T02A writes neither snapshots nor bundles.

## Dry-run-only commands

- `assess_vault_purge`: authenticates `credential.purge`, evaluates at most 100 deleted rows, records safe eligible/blocked counts and a critical `vault.purge_assessed` audit, and never changes a credential.
- `assess_vault_rotation`: authenticates the selected KEK/DEK capability only and does not open or change keys.
- `assess_vault_recovery`: authenticates `recovery.verify` only and does not open backups or keys.
- Every `--execute` option fails before authorization or state mutation with `Execution is not available in IC-023-T02A`.

## Audit vocabulary

Forward vocabulary adds controlled maintenance denial, hold create/release, purge assessment/execution foundation, rotation checkpoint, backup checkpoint, recovery verification, and online-retirement-check actions plus the `vault_maintenance_operation` target type. Maintenance audits link an operation UUID to its opaque operator record. No token, credential metadata, path, key material, or exception text is stored.

## Transaction and lock order

T02A retains the existing user → session/grant → owner key → vault record → audit order. Future globally exclusive maintenance begins with `VaultMaintenanceGuard`, then ordered users, maintenance operation/journal/hold/inventory rows, ordered owner keys, ordered record UUIDs, and critical audit. T02A does not yet acquire the global guard for destructive work because no such work exists.

## Files and migrations

Forward migrations:

- `vault.0004_vaultbackupset_vaultmaintenanceconfirmation_and_more`
- `security_audit.0012_remove_securityauditevent_audit_target_type_known_and_more`

Accepted historical migrations are unchanged.

Implementation touches settings/example configuration, vault models/services/views/routes, lifecycle/maintenance/backup contract modules, command-only management boundaries, audit vocabulary, focused tests, and this record.

## Verification evidence

Environment: Windows, Python 3.13.5, Django 5.2.8, SQLite supplementary tests and native MySQL disposable test database.

- Focused SQLite lifecycle/maintenance coverage: 19 tests, 18 passed, 1 POSIX-only permission test skipped.
- Complete affected SQLite regression (`vault session_auth accounts security_audit`): 201 tests, 172 passed, 29 native/environment/platform skips, no failures.
- Focused restore/re-delete and purged-restore regression: 2/2 passed before inclusion in the authoritative 201-test rerun.
- Native MySQL lifecycle/maintenance suite: 19 tests, 18 passed, 1 POSIX-only permission skip.
- Disposable SQLite migrations: forward apply, rollback of `vault.0004` and `security_audit.0012`, forward reapplication, and `migrate --check` passed; disposable file removed.
- `makemigrations --check --dry-run`: no drift.
- Django system/database check: passed.

Python compilation, Django system/database check, migration drift, tracked whitespace, secret-pattern, production-import, and HTTP-route exposure scans passed. The only sensitive-term scan match was the intentional in-memory read of the protected operator token file; the token is neither logged nor persisted.

## Limitations and residual risks

- Windows and future production-host ACLs require environment qualification; the code fails closed if inspection fails or broad principals are detected.
- The local database snapshot mechanism remains deliberately unselected and must be approved and validated before T02C-3.
- Filesystem/database atomicity will require the approved inventory reconciliation state machine in T02C-3.
- No current command can create a VERIFIED backup inventory; the model constraint only establishes the future evidence boundary.
- No actual purge, rotation, backup, recovery, retirement, or destruction path exists.

## Deferred work

- T02B: frontend lifecycle, grants, reveal/copy memory behavior, accessibility, and browser evidence.
- T02C-1: confirmed bounded purge transition and native concurrency.
- T02C-2: journaled KEK/DEK rotation and retirement guards.
- T02C-3: selected snapshot mechanism, manifest/bundle creation, recovery verification, and reconciliation.
- T02D: consolidated regression, browser/security evidence, and final F-05 documentation.

No staging, commit, push, PR, merge, deployment, or subsequent workstream authorization is implied.
