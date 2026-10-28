# IC-007 — App Admin User Lifecycle

**Status:** G1 design approved; Product Owner authorized IC-007 implementation; G2 remediation complete, re-review pending
**Feature:** F-02 Identity & Administration (G0 planning approved)  
**Priority:** P0  
**Dependencies:** IC-006 invitation/activation and IC-008 audit infrastructure integrated in F-02
**Planner:** SOL  
**Updated:** 2026-10-28

**G2 remediation authorization:** SOL review `5678257033` conditionally passed the reviewed head `75722f0e57d1b896e1a252a1216ec8f4e8609bde` and held G3 pending three corrections. The Product Owner authorized corrections only: common locking for every active-App-Admin membership transition, usable UI pagination, and fail-closed database-session revocation. These corrections refine the approved design without expanding product scope.

## 1. Authoritative source and scope distinction

The original *IT Support Copilot V1.0 | TTDM Development Specification*, **IC-007 | App Admin account lifecycle**, specifies:
- **Objective:** Implement provisioning, deactivation, reactivation and protected deletion initiation.
- **Implementation scope:** Admin-only user list/create/update, session revocation, last-admin protection, explicit deletion review flow.
- **Acceptance:** Non-admin denied; deactivation immediately blocks access; reactivation restores only authorized access; last active App Admin cannot be deleted.
- **Verification:** Permission matrix, session invalidation tests, UI admin flow.
- **Dependency:** IC-006. **Risk:** Avoid cascades affecting shared documentation.

The original specification does **not** prescribe endpoint paths, lifecycle schema, revocation mechanism, retention policy, deletion approval workflow, or exact concurrency implementation. Sections 2–8 originated as **SOL-proposed G1 details**. The Product Owner first approved all seven design recommendations on 2026-10-28 for specification planning, then explicitly authorized IC-007 implementation in the current assignment. F-02 G0 separately approves decisions F02-D04 through F02-D08.

## 2. Boundaries and prerequisites

**In scope:** Active App Admin-only user listing and details; controlled provisioning through the approved IC-006 invitation path; authorized edits to permitted user attributes and role flags; deactivation/reactivation; server-side session revocation and immediate authorization denial; transactional last-active-App-Admin guard; non-destructive deletion review initiation; audit event integration; minimal `/admin/users` UI; four TTDM living documents and tests.

**Out of scope:** Permanent deletion, cascading document/vault cleanup, retention purge, password reset, user self-registration, bulk operations, ownership transfer, vault access, production deployment. IC-024 remains blocked on both IC-007 and IC-023; this task must not implement IC-024.

**Prerequisites for implementation/integration:** IC-006 invitation/activation service and IC-008 structured audit service implemented under separately approved gates; F-01 custom User/session/CSRF/policies remain authoritative. G1 documentation approval alone does not satisfy these runtime dependencies.

## 3. Proposed roles and lifecycle model

- App administration requires **authenticated, active `User.is_app_admin=True`**. `it_role` (including `IT_DOC_ADMIN`) does not confer App Admin authority. `is_staff` and `is_superuser` are not substitutes for this application policy.
- User list/details expose only a bounded administrative profile (id, email, `is_active`, `is_app_admin`, `it_role`, lifecycle status); no passwords, session IDs, invitation secrets, vault secrets, private document content or raw audit payloads.
- Provisioning delegates to **IC-006**: invite a canonical email, assign initial `it_role` and optional App Admin flag, create pending inactive user; no direct creation of an active user with a supplied plaintext password.
- **G1-approved direction:** distinguish `pending_invitation` from `deactivated` using an explicit lifecycle marker or equivalent durable provenance; `is_active=False` alone is ambiguous. Never reactivate an unactivated pending invitation through the reactivation endpoint.
- Deactivation changes an active user's state to inactive and invalidates all of their database-backed sessions, including concurrent devices. A deactivated user must fail authentication and every protected API authorization check immediately; existing CSRF tokens cannot restore access.
- Reactivation is an explicit App Admin action on a previously activated, deactivated account. It does not create a session, reset password, restore expired invitations, grant new roles or bypass ownership checks. The user must log in again.
- Changes to `is_app_admin` and `it_role` are server-validated, audited, and subject to last-admin protection. An App Admin has no implicit right to another user's private IT documentation or vault.

## 4. Last-active-App-Admin invariant and concurrency

**G0-approved invariant:** At least one **active, activated App Admin** must remain after any administrative mutation, including deactivation, role downgrade and any future deletion. Pending/inactive invitees do **not** count.

**G1-approved architecture direction:** perform last-admin-affecting mutations inside a MySQL transaction with a serialization mechanism that covers *all* concurrent admin-removal requests (e.g. a dedicated singleton guard row locked with `SELECT ... FOR UPDATE` before counting and updating). Locking only the target user or counting without a shared lock is insufficient. Audit success record and mutation commit atomically; audit persistence failure aborts the mutation.

**Edge cases:** self-deactivation, two concurrent admins deactivating each other, concurrent role downgrades, retry after database conflict, and pending App Admin invitation not counting toward the active-admin minimum. Denials use a safe stable error, with bounded sanitized denied-attempt audit where feasible.

## 5. Session revocation and authorization semantics

**G1-approved direction:** use a revocation strategy compatible with Django's existing database session backend. Because session records may not directly index user IDs, define and test a reliable server-side mapping or revocation generation mechanism that invalidates **all** sessions for the target user, including concurrent requests. Explicitly document the chosen implementation and ensure no plaintext session key appears in audit or application logs.

- Deactivation must persist before the response reports success; requests starting afterward must be denied immediately.
- Role downgrades and App Admin flag removal must take effect on the next protected request, even if a session remains valid; never rely on cached frontend role state.
- Session revocation on reactivation is **not** reversed; user authenticates afresh.
- Session failure, partial invalidation, and audit persistence failure need failure-injection tests. Prefer fail-closed transaction semantics for security-critical changes.

## 6. Proposed API and UI contracts

Maintain DRF JSON error envelope `{"error":{"code":"...","message":"..."}}`, cookie sessions and CSRF protection on mutations. All routes below are **proposals**, not pre-existing endpoints.

| Route | Access | Success | Errors |
| --- | --- | --- | --- |
| `GET /api/v1/users` | Active App Admin | `200 {"users":[{"id":1,"email":"user@example.test","is_active":true,"is_app_admin":false,"it_role":"IT_MEMBER","lifecycle_status":"active"}]}` | `401 authentication_required`, `403 permission_denied` |
| `GET /api/v1/users/{id}` | Active App Admin | `200 {"user":{...}}` | `401/403/404` |
| `PATCH /api/v1/users/{id}` | Active App Admin + CSRF | `200 {"user":{...}}` | `400 invalid_request`, `403 permission_denied/csrf_failed`, `404 not_found`, `409 last_active_admin` |
| `POST /api/v1/users/{id}/deactivate` | Active App Admin + CSRF | `200 {"user":{...}}` | `400 invalid_state`, `404 not_found`, `409 last_active_admin` |
| `POST /api/v1/users/{id}/reactivate` | Active App Admin + CSRF | `200 {"user":{...}}` | `400 invalid_state`, `404 not_found` |
| `POST /api/v1/users/{id}/deletion-reviews` | Active App Admin + CSRF | `202 {"review":{"id":"<opaque>","status":"pending_review"}}` | `400 invalid_state`, `404 not_found`, `409 last_active_admin` |

- **Create user:** reuse approved IC-006 `POST /api/v1/users/invitations`; do not introduce an independent active-user creation bypass. This satisfies the source's admin-only create/provisioning scope via invitation.
- **G1-approved PATCH allowlist:** `it_role` and `is_app_admin` only; email edits require a separate identity-verification design and are excluded from this task unless PO explicitly adds them. `is_active` must be changed only through explicit lifecycle actions, not generic PATCH.
- **Deletion review initiation:** create a non-destructive review record only, with requester ID, target ID, reason code, status and timestamps. No hard/soft deletion, disabling, ownership changes, cascades or background cleanup occur by initiating review. Review cannot be mistaken for permission to execute deletion; execution is IC-024.
- **G1-approved UI direction:** `/admin/users` for list, invite, edit roles, deactivate/reactivate, initiate deletion review with explicit confirmation. Hide controls from non-admins for usability but enforce backend checks. Show safe success/error states and require explicit confirmation for destructive-intent requests.
- For list API, **G1-approved pagination direction:** bounded pagination (default 20, max 100), deterministic ordering, and no search across private documents. Actual MVP <=10 users but avoid unbounded responses.

## 7. Audit and privacy contract

IC-008's controlled event vocabulary must be extended through a reviewed versioned contract for `account.deactivated`, `account.reactivated`, `account.role_changed`, `account.deletion_review_requested` and `authorization.denied`; existing `account.invite_created` remains owned by IC-006. Use actor/target nonsecret ID snapshots and allowlisted outcome/timestamps. Never record passwords, email addresses, IP addresses, session keys, cookies, token values/hashes, raw request bodies, document/vault contents, or unrestricted free text.

For successful sensitive mutations, **state change and audit event must commit atomically**; on audit persistence failure, fail closed. Denied attempts are bounded best-effort outside rolled-back transactions. No audit retention period or purge is authorized.

## 8. G1-approved acceptance criteria and verification

| ID | Acceptance criterion | Evidence |
| --- | --- | --- |
| IC-007-AC-01 | Only active App Admin can list, inspect or mutate user lifecycle; IT roles alone confer no admin access | Role matrix incl. anonymous, inactive, IT_DOC_ADMIN and cross-role tests |
| IC-007-AC-02 | Provisioning uses IC-006 invitation; no active-user creation or self-registration bypass | Route inventory and API integration |
| IC-007-AC-03 | List/detail responses expose bounded safe fields; no secrets/private resources | Serialization and sentinel-secret tests |
| IC-007-AC-04 | Admin edits only allowlisted fields; changes are validated, authorized and effective on next request | API and role downgrade tests |
| IC-007-AC-05 | Deactivation immediately blocks all active sessions and subsequent protected API access | Multi-session revocation and CSRF/auth regressions |
| IC-007-AC-06 | Reactivation applies only to previously activated, deactivated accounts and requires fresh login | State transition and session tests |
| IC-007-AC-07 | Last active App Admin cannot be deactivated or downgraded, including self-action | Invariant and denial tests |
| IC-007-AC-08 | Concurrent App Admin mutations cannot jointly remove the last active App Admin | Native MySQL transaction/concurrency tests |
| IC-007-AC-09 | Deletion initiation creates only a review record, no deletion/cascade/session change | DB diff, ownership and vault-scope negative tests |
| IC-007-AC-10 | Sensitive lifecycle changes are audited atomically without secrets; audit failures fail closed | Audit assertions and failure injection |
| IC-007-AC-11 | Admin UI covers invite, list, edit, deactivate, reactivate and deletion-review initiation | Browser workflow and unauthorized UI/API tests |
| IC-007-AC-12 | Native MySQL migrations/regressions, CSRF, existing IC-003/004/006/008 behavior and four TTDM docs verified | Exact commands, counts, PR head and SOL review |

## 9. Product Owner-approved G1 design decisions — 2026-10-28

The following list preserves the original G1 planning approval; the later IC-007 assignment supplies implementation authorization:

1. **Lifecycle state:** durable distinction between `pending_invitation` and `deactivated`; `is_active=False` alone is insufficient.
2. **Session revocation:** invalidate every session on deactivation; require fresh login after reactivation. The precise mechanism must be proven against the existing Django database session backend.
3. **Last-active-App-Admin invariant:** shared-lock transaction serialization for all admin-removal mutations; pending invitees do not count.
4. **Editable attributes:** `it_role` and `is_app_admin` only; email edits and password reset deferred.
5. **Deletion review:** non-destructive review record only; no execution, deletion, disabling, or cleanup until separately approved IC-024.
6. **API/UI:** Section 6 routes, `/admin/users` page, explicit confirmation, and bounded pagination.
7. **Audit:** controlled/versioned lifecycle event additions, atomic audited success mutations, and sanitized bounded denied-attempt recording.

**Approval boundary:** IC-007 implementation only. Merge remains prohibited until SOL G2/G3 review and separate Product Owner exact-head approval.

## 10. TTDM gate and review

- **G0:** F-02 scope and F02-D04 through D08 approved for planning.
- **G1:** The Product Owner approved the seven design recommendations on 2026-10-28. A later assignment explicitly authorized IC-007 implementation while preserving these decisions.
- **G2/G3:** Implementation evidence is recorded in the living documents; SOL review is pending.
- **Merge:** The IC-007 draft implementation PR must remain unmerged until separate exact-head PO authorization after SOL review.
- **IC-024:** Permanent deletion and cleanup explicitly deferred until IC-023 and separate task approval.
