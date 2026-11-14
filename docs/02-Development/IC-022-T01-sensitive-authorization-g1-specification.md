# IC-022-T01 — Sensitive authorization G1 specification

**Status:** PRODUCT OWNER G1 APPROVED — IC-022 T02A–T02C implementation complete in worktree

**Baseline:** `6164b2862056d697d91beb579fbaf467c409c21a`

**Branch:** `feature/ic-022-sensitive-authorization-grants`

**Parent contract:** [F-05 consolidated G1 proposal](../features/F-05-consolidated-g1-proposal.md)

## Architecture discovery

The baseline uses Django database sessions, Django password hashing, DRF session authentication, CSRF protection, exact-origin credentialed CORS, active-account checks, and owner-scoped vault queries. IC-021 provides encrypted create/update/reveal/delete/restore services, critical audit atomicity, generic unavailable behavior, and a post-commit plaintext barrier. Production-sensitive routes were deliberately disabled and `vault.authorization` denied every request.

Account deactivation deletes the user's database sessions. Logout invalidates the exact current session. No public password-change/reset endpoint exists. Test authorization support is isolated at `vault.tests.testing`; production code must never import it. The repository has no production artifact build mechanism that independently proves `vault/tests/**` exclusion.

## Approved decisions

1. One `VAULT_SENSITIVE` grant scope authorizes exactly one committed create, update, reveal, delete, or restore operation.
2. A dedicated server-only `VAULT_GRANT_PEPPER` provides domain-separated keyed proof and session digests. Rotation invalidates grants fail closed.
3. IC-022 supplies reusable user-wide revocation for a future password-change transaction but adds no password-change/reset endpoint.
4. Logout revokes exact-session grants and records one controlled grant-revocation audit without unbounded per-grant events.
5. Production modules may not import `vault.tests.testing`. With no existing production packaging mechanism, validation consists of an import/source scan and a documented artifact-exclusion requirement.

## Contract

- `POST /api/v1/vault/reauthenticate` verifies the current account password in the exact active session and returns a random proof once. Grants expire after an absolute two minutes.
- Password failures are limited to five per user and per session digest in a fixed 15-minute window. Issuance is limited to ten per user per fixed 15 minutes and three live grants per session.
- Only proof and session HMAC-SHA-256 digests are persisted; raw proof, raw session key, password, credential ID, plaintext, and key material are prohibited.
- `X-Vault-Grant` carries the proof. Validation occurs under the sensitive operation transaction after locking user and exact session, then grant, vault key, record, and finally inserting critical audits.
- A valid grant is consumed on business rejection. Crypto, database, critical-audit, or commit failure rolls back consumption. Invalid/replayed/revoked/expired/wrong-session proofs do not transition.
- `POST /api/v1/vault/grants/revoke` revokes current-session grants idempotently. Logout and account deactivation revoke grants transactionally. Every use independently validates the bound database session.
- App Admin, staff, superuser, and IT roles never bypass ownership or grant validation.
- Reveal plaintext cannot enter response construction before grant consumption and critical reveal audit commit.

## Boundaries

IC-023 frontend reveal/copy behavior, rotation, recovery, backup manifests, purge, key retirement, account deletion, deployment, Redis, Celery, external KMS, and external secret infrastructure remain excluded.
