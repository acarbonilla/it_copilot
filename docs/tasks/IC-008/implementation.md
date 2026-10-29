# IC-008 implementation

**Status:** SOL G2 conditional findings remediated; re-review pending
**Date:** 2026-10-28
**Branch:** `task/IC-008-audit-authorization-harness`
**Base:** `feature/identity-administration` at `5a5c56e819cb11ebc203c1fc57b7a0a229a74b32`
**Implementation commit:** `3385812fdccbb377282c482772af51042db7b068`
**Draft PR:** #13 targeting `feature/identity-administration`
**G2-reviewed head:** `d9ab7b23c0ef8eb2eeeb790625d71da4750660a3`

## Delivered design

- Added the `security_audit` Django app and `SecurityAuditEvent` migration. Events contain only a controlled action, nullable positive actor ID snapshot, controlled target type, constrained opaque target ID, controlled outcome, timestamp, and optional UUID correlation ID.
- Actor attribution is a scalar snapshot, not a foreign key. Instance update and deletion are rejected; no purge or audit-viewing route exists.
- Added `record_security_event` with an explicit keyword-only allowlist and validation. There is no metadata, request, email, address, credential, header, cookie, session, payload, or exception-message field.
- Target IDs accept only positive decimal identifiers or canonical hex/UUID identifiers. Request IDs accept only canonical hex/UUID identifiers. This keeps free text and common secret-bearing values out of the schema.
- Added `record_critical_event`, which requires an active Django atomic transaction and propagates validation/database failures so the mutation rolls back.
- Added `record_denied_event_best_effort`, which performs one autocommit attempt, returns `None` on failure, and emits only a constant warning without exception content or supplied field values. It refuses to insert inside an atomic block or when autocommit is disabled, preventing an apparently recorded denial from disappearing in a later rollback.
- Added deterministic factories and authorization matrices for anonymous, inactive, unknown-role, cross-owner, App Admin, and known IT-role subjects.
- Preserved existing session authentication, CSRF middleware, role/ownership policies, routes, and structured API errors. IC-004 authentication handlers were deliberately not changed.

## Scope exclusions preserved

No IC-006 invitation workflow, IC-007 lifecycle endpoint, IC-024 deletion behavior, audit viewing/export API, retention job, deployment change, or new route was introduced. Initial event vocabulary reserves the G1-approved names but does not implement the future operations that emit them.

## Vocabulary and identifier evolution

Event vocabulary is a database-enforced, versioned contract. An owning future task must document each new action/target meaning, add it to model choices and value tuples, create a new forward migration for the database constraints, add rejection/persistence/migration/sanitization tests, and receive its own PO authorization plus SOL review. Applied migrations are never rewritten.

Numeric account IDs work with the existing `account` target. Canonical UUID and 32-character lowercase hexadecimal values are accepted for a planned opaque IC-006 invitation identifier, but IC-006 must add an `account_invitation` target type if the invitation itself—not its account—is the target. Any different opaque format requires a reviewed IC-008 compatibility change. IC-007's planned account mutations use numeric account IDs already accepted by the service. No IC-006/007 action emission was added here.

## Migration

`security_audit.0001_initial` creates one table, four database check constraints, and action/time and actor/time indexes. The native configured MySQL database applied it once; the second migrate reported `No migrations to apply`, and `migrate --check` exited successfully.

## Implementation notes

The caller owns the mutation and must call `record_critical_event` inside the same `transaction.atomic()` block. Denials must call the best-effort function only after leaving the mutation transaction; the service enforces this by requiring autocommit and refusing to insert otherwise. Retention remains intentionally undefined and unimplemented pending a separate Product Owner decision.
