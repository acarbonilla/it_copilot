# IC-006 implementation

**Status:** SOL G2 conditional findings remediated; exact-head re-review pending
**Date:** 2026-10-28
**Branch:** `task/IC-006-invitation-activation`
**Base:** `feature/identity-administration` at `726edee0312a6ad5522c1bf1aa08936477386336`
**Implementation commit:** `dfcb77c281480154ac1a7c10cd631e6e182fb16e`
**G2-reviewed head:** `54e55ee16ee22a628b4477867c28c5a218832806`
**G2 remediation commit:** `91485fef60ef47adbb35373deef59427327d02dd`
**Draft PR:** #14 targeting `feature/identity-administration`

## Backend design

- `accounts.User.lifecycle_state` distinguishes `PENDING_INVITATION` from existing active/legacy accounts. A pending user is inactive and has an unusable password. Existing rows migrate to `ACTIVE`; an inactive `ACTIVE` account is not invitation-eligible and cannot be silently reactivated.
- `AccountInvitation` uses a UUID primary key, protected user reference, unique SHA-256 token digest, 24-hour expiry, consumed/revoked timestamps, and immutable inviter ID snapshot. Raw tokens never enter the database.
- Token secrets use `secrets.token_urlsafe(32)` (256 bits). Only the SHA-256 digest is used for lookup. Token shape is bounded before hashing.
- Invitation/re-invitation locks the account, revokes every outstanding token, updates pending grants, creates the new invitation, records `account.invite_created`, and writes the local delivery artifact in one guarded operation. Database or audit/delivery failure rolls back; partial delivery files are removed.
- Activation locks both invitation and account with `SELECT ... FOR UPDATE`, validates state and expiry, applies the configured Django validators, hashes the password, activates the account, consumes the invitation, and records `account.activation_succeeded` in one transaction.
- Invalid, expired, revoked, reused, unknown, and malformed secrets share `400 invalid_activation`. A valid token with a weak password receives the approved bounded `password_policy_failed` response and remains usable after a stronger password is chosen.
- Activation never calls Django `login`; no session is created.

## Authorization and API

- `POST /api/v1/users/invitations` requires an active session user whose role is known and whose independent `is_app_admin` flag is true. Django session authentication and CSRF remain authoritative.
- `POST /api/v1/auth/activate` is anonymous but explicitly CSRF-protected. Both endpoints retain the established structured JSON error envelope.
- There is no registration, signup, generic user-creation, user-listing, lifecycle administration, deletion, audit-reading, or retention route.
- The invitation response contains only UUID, `pending` status, and expiry. It never contains the raw token, digest, activation URL, email, or password.

## Audit vocabulary

`security_audit.0002_ic006_event_vocabulary` is a forward migration that adds `account.activation_succeeded`, `account.activation_denied`, and `account_invitation`, recreating only the controlled database constraints. The original applied IC-008 migration is unchanged. Success events are transactional; denial events use the IC-008 autocommit-only best-effort service after failed activation transactions exit.

## Development delivery procedure

Delivery defaults to disabled. A local developer must explicitly set `DJANGO_DEBUG=true` and `INVITATION_DELIVERY_MODE=file`. Each invitation creates one mode-`0600` JSON artifact under ignored `tmp/invitations` by default, named with the nonsecret invitation UUID. The operator retrieves that file locally, never through an API. Files must not be served, logged, committed, synced, or shared; delete used artifacts and clear stale/revoked artifacts after the verification session. Windows host ACLs remain operator-controlled because POSIX mode bits alone are not a Windows security boundary.

Cleanup tracks whether the current call successfully completed exclusive creation. `FileExistsError` therefore preserves an existing path and rolls the database back. Partial writes and caught database commit failures delete only the newly owned artifact. Database commit and filesystem persistence cannot be made durably atomic without a transactional delivery store: a process/host crash between write and commit can orphan a file whose token has no committed digest, while file loss after commit has no automatic retry. The local-only sink, unusable orphan tokens, exclusive creation, and mandatory cleanup bound—but do not eliminate—that residual.

## Frontend

Next.js route `/activate/[token]` awaits the Next.js 16 dynamic params contract and renders a password/confirmation form. Production response inspection with a fake sentinel found three token occurrences, all inside Next.js hydration scripts and none in non-script HTML or visible text. The client uses the existing CSRF bootstrap/retry client, immediately replaces the address/history entry with tokenless `/activate`, sends credentials only to the activation endpoint, and replaces the entry with `/login` after success. It does not authenticate. Both page metadata and a route-specific HTTP header set `Referrer-Policy: no-referrer`; the page has no third-party assets. Initial network URLs, serialized response source, browser developer tools, process memory, and future access logs can still contain the token and remain within the local-only trust boundary.

## Scope preserved

No IC-007 user administration, IC-024 deletion, credential vault, hosted deployment, external mail, audit viewing/retention, or unrelated authentication change was implemented.
