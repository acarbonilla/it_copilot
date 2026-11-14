# IC-022-T02 — Sensitive authorization implementation

**Status:** IC-022 T02A–T02C IMPLEMENTED AND DEVELOPER-VERIFIED IN WORKTREE

**Starting baseline:** `6164b2862056d697d91beb579fbaf467c409c21a`

**Branch:** `feature/ic-022-sensitive-authorization-grants`

## Scope and exclusions

T02A implements only grant/throttle persistence, server-only digest configuration, proof issuance, exact-session verification at issuance, password reauthentication, throttling/caps, controlled issuance audit, focused tests, and living documentation.

T02B enables create, update, reveal, delete, and restore through transaction-bound single-use grants. T02C adds explicit current-session revocation, logout and deactivation integration, aggregate critical revocation audit, invalid-session enforcement, and reusable user-wide revocation for a future password-change transaction. IC-023 and deployment scope remain excluded.

## Approved decisions and security invariants

- Scope is the controlled `VAULT_SENSITIVE` value.
- A dedicated mandatory non-test `VAULT_GRANT_PEPPER` keys domain-separated proof and session HMAC-SHA-256 digests.
- Pepper rotation invalidates outstanding grants fail closed.
- Raw proof, raw session key, password, credential identifier, plaintext, ciphertext, and encryption keys are not persisted or audited.
- Reauthentication uses Django password hashing, does not rotate the session, and verifies the exact active database session.
- Grants expire by absolute server time two minutes after issuance.
- Critical audit failure rolls back issuance and throttle changes.
- Production code does not import `vault.tests.testing`.

## Data model and migrations

`SensitiveOperationGrant` stores UUID identity, protected user, 64-character proof/session digests, controlled scope, issue/expiry timestamps, nullable future consumption/revocation timestamps, and controlled future revocation reason. Constraints enforce expiry ordering, matching revocation fields, and exclusive terminal states. Indexes support user/session live-grant queries.

`UserReauthenticationThrottle` stores one per-user failure window/count and issuance window/count. `SessionReauthenticationThrottle` stores a unique user/session-digest failure window/count.

Forward migrations:

- `vault.0003_userreauthenticationthrottle_sensitiveoperationgrant_and_more`
- `security_audit.0011_remove_securityauditevent_audit_action_known_and_more`

Accepted historical migrations are unchanged.

## Reauthentication API

`POST /api/v1/vault/reauthenticate`

- Requires active session authentication and CSRF.
- Accepts a JSON object containing string `password`.
- Success: `201 {"grant":"<opaque-proof>","expiresAt":"<UTC timestamp>"}`.
- Headers: `Cache-Control: no-store, private`, `Pragma: no-cache`, `X-Content-Type-Options: nosniff`.
- Ordinary denial: fixed `403 reauthentication_failed`.
- Threshold denial: fixed `429 reauthentication_failed` with coarse whole-minute `Retry-After`.
- Malformed and blank password values count after session/CSRF validation.

## Throttle and issuance rules

The service locks user, exact session, user throttle, then session throttle. Fixed windows reset when `now >= window_start + 15 minutes`. The fifth failure is the threshold request and is throttled. A successful password check resets both failure counters. Issuance is limited to ten per user per fixed 15-minute window and three unexpired/unconsumed/unrevoked grants per exact session. MySQL user-row serialization prevents cap races.

## Audit behavior

Controlled vocabulary adds:

- `vault.reauthentication_succeeded`
- `vault.reauthentication_denied`
- `vault.grant_issued`

Successful issuance and both success events share one transaction. Denials update throttle state and write the controlled denial event in one transaction. No sensitive input or digest is included.

## Files changed

- `.env.example`
- `apps/api/config/settings/base.py`, `test.py`, and `urls.py`
- `apps/api/vault/models.py`, `grants.py`, `views.py`, migration, and focused tests
- `apps/api/security_audit/models.py` and forward migration
- Both IC-022 living documents

## Verification evidence

- Django system check: PASS.
- Focused T02A SQLite foundation/API/production-deny suite: 19 tests run, 17 passed, 2 native-only tests skipped.
- Final SQLite `vault session_auth security_audit` regression: 83 tests run, 78 passed, 5 native-only/environment skips, no failures.
- Native MySQL T02A concurrency: 2 tests run, 2 passed using independent worker connections. Coverage includes the five-failure threshold, three-live-grant cap, and ten-issuance cap.
- Migration drift: PASS, no changes detected.
- Disposable SQLite migration verification: full forward apply, rollback of `vault.0003` and `security_audit.0011`, and forward reapplication all passed. The disposable database was removed.
- `git diff --check`: PASS; one Windows LF-to-CRLF warning for `vault/views.py`, no whitespace errors.

## Defects discovered and remediation

- Concurrent throttle-row creation uses a nested savepoint so a uniqueness race cannot poison the outer issuance transaction.
- The threshold calculation was corrected so the fifth failure is immediately throttled.
- Native MySQL tests explicitly inject a test-only pepper; production settings retain no fallback.
- The first combined MySQL concurrency run produced one non-reproduced worker outcome in the issuance-cap test. The isolated test then passed, followed by a clean 2/2 full-class rerun. No implementation relaxation was made.
- The first disposable SQLite migration command targeted a nonexistent worktree `tmp` directory and failed before opening or changing a database. Verification was rerun successfully in the system temporary directory.

## Risks and limitations

- The repository has no production artifact packaging/build mechanism. Source/import isolation is testable, but exclusion of `vault/tests/**` from a future deployment artifact is not yet provable. Future artifact validation must enumerate contents and fail on `vault/tests/`.
- No public password-change/reset endpoint exists; the reusable revoke-all helper is ready for its future approved transaction.

## T02B transaction-bound enforcement

`X-Vault-Grant` accepts exactly one 43-character URL-safe proof. Missing, malformed, oversized, expired, revoked, consumed, wrong-user, and wrong-session proofs return generic `invalid_grant` before target lookup and do not transition the grant. The service locks user → exact session → grant → owner key → record → critical audit.

A valid grant is consumed with `vault.grant_used` in the same commit as a successful create, update, reveal, delete, or restore. Payload, ownership, lifecycle, missing-target, and revision rejection consumes the grant with `vault.grant_denied` while leaving the target unchanged. Crypto, database, grant-audit, vault-audit, or commit failure rolls back grant and target state. Database lock timeout/deadlock retry is bounded to two complete pre-commit attempts for issuance and sensitive services.

Reveal preserves `DeferredReveal`: plaintext decryption/release occurs only from the post-commit callback after grant consumption and critical reveal audit commit. Reveal responses carry no-store/private, no-cache, and nosniff headers.

### T02B verification

- Focused SQLite T02B service/API/security suite: 36 tests run, 35 passed, 1 native-MySQL test skipped.
- Complete final SQLite vault regression after T02B: 58 tests run, 52 passed, 6 native-only skips, no failures.
- Additional expiry/revocation/wrong-session and grant-audit rollback suite: 7/7 passed.
- Native MySQL final concurrency set: 3/3 passed using independent connections—failure threshold, both issuance caps, and simultaneous single-grant consumption.
- The first combined MySQL run exposed a lock-wait timeout in the five-way password race; issuance received the same bounded two-attempt pre-commit retry policy, after which the authoritative 3/3 rerun passed.

## T02C handoff

T02C is complete. `POST /api/v1/vault/grants/revoke` is authenticated, CSRF protected, exact-session-bound, idempotent, and returns `204`. Logout revokes current-session grants before invalidating the session. Account deactivation locks affected sessions in stable order, deletes them, revokes outstanding grants, and commits account and grant audits atomically. `revoke_all_user_grants()` is the integration point for a future password-change transaction; callers must already hold user and affected-session locks.

Expired, deleted, corrupt, undecodable, and wrong-user sessions cannot validate grants. Revocation writes one aggregate `vault.grant_revoked` critical event, including idempotent zero-grant requests, rather than an unbounded event per grant. Audit failure rolls back revocation and lifecycle/session effects.

Password hashing is performed for every reauthentication input before row locking, then the transaction revalidates that the locked user's stored password hash exactly matches the hash checked. A concurrent password change therefore fails closed while keeping MySQL lock duration bounded.

### Final IC-022 verification

- Focused T02C SQLite revocation/session/account suite: 35 tests run, 32 passed, 3 native-only skips, no failures.
- Combined SQLite regression (`vault session_auth accounts security_audit`): 180 tests run, 152 passed, 28 environment/native-only skips, no failures.
- Affected reauthentication suite after contention remediation: 8/8 passed.
- Consolidated native MySQL concurrency: 7/7 passed using independent connections. Coverage includes failure threshold, both issuance caps, single-grant double use, use versus explicit revoke, use versus logout, use versus deactivation, and forced revocation-wins/use-wins ordering.
- Migration drift: no changes detected.
- Disposable SQLite migrations: forward apply, rollback of `vault.0003` and `security_audit.0011`, and forward reapplication all passed. The disposable database was removed.
- Django system check and `git diff --check`: passed; one Windows LF-to-CRLF warning only.
- Secret/import scan: no production `vault.tests` import and no password, raw proof, raw session key, or plaintext logging path found.

### Packaging boundary

The repository has no backend Dockerfile, Python packaging manifest, `pyproject.toml`, `setup.py`, `MANIFEST.in`, or other production artifact mechanism. Exclusion of `vault/tests/**` therefore cannot be independently verified. A future artifact gate must enumerate contents, fail if `vault/tests/` is present, and scan production modules for `vault.tests` imports.

### Remaining handoff

IC-022 implementation is complete. IC-023 retains frontend reveal/copy lifecycle, rotation, recovery, purge, backup-manifest, and key-retirement work.

## Exact-head checkpoint

Verified working-tree base/HEAD: `6164b2862056d697d91beb579fbaf467c409c21a`. IC-022 changes remain unstaged and uncommitted. No staging, commit, push, PR, merge, or deployment is authorized.
