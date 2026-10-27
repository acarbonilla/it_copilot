# IC-006 — Account Invitation and Activation

**Status:** Draft — G1 Product Owner approval pending; implementation not authorized  
**Feature:** F-02 Identity & Administration (G0 planning approved)  
**Priority:** P0  
**Dependencies:** IC-003 custom user/roles and IC-004 session auth/CSRF (F-01 complete); IC-008 audit integration is a F-02 sequencing constraint  
**Owner:** SOL specification planning; Codex implementation not authorized  
**Updated:** 2026-10-27

## 1. Source-derived requirement

The original *IT Support Copilot V1.0 | TTDM Development Specification*, **IC-006 | Invitation and activation**, defines:
- **Objective:** Enable App Admin-provisioned accounts without self-registration.
- **Implementation scope:** Single-use hashed activation token, expiry, initial password setup, generic error behavior, development-safe email output.
- **Acceptance:** Only App Admin can invite; token single-use and expires; initial password meets policy; invitation does not disclose tokens in logs.
- **Verification:** API tests for expired/reused tokens and unauthorized invitation.
- **Dependencies:** IC-003 and IC-004. **Risk:** Token disclosure or enumeration.

Everything below is **SOL's proposed G1 contract**, not additional wording from the original specification. Product Owner must approve choices before implementation.

## 2. Scope and exclusion

**In scope (proposed):** Admin-only invitation initiation; pending inactive account state; one-time token issuance and validation; secure initial password setup and activation; development-only delivery adapter; audit integration contract; minimal activation frontend; repeatable security/API/browser tests and four TTDM living documents.

**Out of scope:** Public sign-up, account recovery/password reset, invitation bulk import, external email service, account lifecycle management after activation (IC-007), vault or document access grants beyond existing role policy, permanent deletion (IC-024), hosted deployment.

**Security boundaries:** `is_app_admin` is independent of `it_role`; an IT documentation administrator is not automatically an App Admin. Backend authorization is authoritative. Existing authenticated session/CSRF behavior must not regress.

## 3. Proposed workflow and state machine

1. An **active authenticated App Admin** submits an invite request for an email address and explicitly selected initial `it_role` and `is_app_admin` flag. The latter is privileged; only App Admin may grant it. **G1 decision:** whether IC-006 should permit inviting another App Admin at all, or reserve elevation for IC-007.
2. Server canonicalizes email exactly as `accounts.User` does; performs duplicate/inactive/pending-account checks without revealing account existence to unauthorized users. A unique user identity must not be duplicated.
3. Create a pending **inactive** user with an unusable password and a random activation secret. Store **only a cryptographic digest** of the secret, expiration timestamp, issuance/consumption timestamps, and reference to the intended user; never persist the raw token.
4. Generate an activation link to the local Next.js route `/activate/[token]`. The development-safe delivery adapter may show the link in a controlled local mailbox/file sink **only in explicitly configured development mode**, not application logs or production-like output. Clarify local developer retrieval procedure before G1 approval.
5. On activation submit, atomically validate digest match, not expired, not consumed, and user eligible; apply Django password validators and approved minimum password policy; set password, activate user, consume token in one transaction, and write the required audit event in that transaction.
6. Replay, expired, revoked, unknown, or malformed token attempts receive a uniform safe response. They do not activate accounts or reveal whether a user exists. A new invitation must invalidate older unconsumed tokens for that user.
7. Activation **does not automatically authenticate** the user. Redirect to login; normal IC-004 session/CSRF flow remains the only login path.

**State transitions (proposed):** `NO_ACCOUNT → PENDING_INACTIVE → ACTIVE`; `PENDING_INACTIVE → EXPIRED/REVOKED → PENDING_INACTIVE` via authorized re-invite. Deactivated existing accounts must **not** be reactivated by invitation; that belongs to IC-007.

## 4. Proposed data and service design

- Existing `accounts.User` retains unique canonicalized email, `is_active`, `is_app_admin`, `it_role`, password hash. Pending invite users must have `is_active=False` and `set_unusable_password()`.
- Proposed `AccountInvitation` table: opaque primary key, user reference, token digest (unique), `created_at`, `expires_at`, `consumed_at` (nullable), `revoked_at` (nullable), `invited_by_user_id` immutable nonsecret snapshot. No raw token, email or request body in audit metadata.
- Generate token with a cryptographically secure random generator, at least 256 bits entropy; store SHA-256 digest or a suitable keyed digest, use constant-time comparisons where applicable. Never put token in analytics, exception traces, server logs or referrer-bearing outbound links.
- Expiry **proposed: 24 hours** from issuance. This is not source-mandated and requires PO confirmation.
- Enforce concurrency safety: consume via transaction/row locking or conditional update; two simultaneous activation attempts cannot both succeed. Account creation, invitation, and audit success event must be atomic. If critical audit persistence fails, fail closed.
- Avoid emailing secrets to external recipients in local-only MVP. Restrict delivery sink and document cleanup of development-only token artifacts.
- Token URLs must not be stored in browser history beyond what is required for activation; use `Referrer-Policy: no-referrer` and avoid third-party resources on activation page. Do not log token-containing request paths.

## 5. Proposed API and frontend contract

Existing API conventions: DRF JSON, structured `{"error":{"code":"...","message":"..."}}`, session auth and CSRF, browser origin `http://localhost:3000`.

| Route | Actor | Success | Failure |
| --- | --- | --- | --- |
| `POST /api/v1/users/invitations` | Active authenticated App Admin only; CSRF required | `201 {"invitation":{"id":"<opaque>","status":"pending","expires_at":"<ISO8601>"}}` | `401 authentication_required`, `403 permission_denied/csrf_failed`, `400 invalid_request`, `409 invitation_conflict` |
| `POST /api/v1/auth/activate` | Anonymous; CSRF required for browser POST | `200 {"status":"activated"}` | `400 invalid_activation` for unknown/expired/reused/revoked; `400 password_policy_failed` for valid token with weak password |

**Request examples (proposed):**

```json
{"email":"invitee@example.test","it_role":"IT_MEMBER","is_app_admin":false}
```

```json
{"token":"<secret-from-invitation-link>","password":"<initial-password>"}
```

- The invitation API must **never return the activation secret or URL** in its JSON response. A privileged developer-only delivery mechanism is separate.
- Invite conflicts should avoid revealing existing users to unauthorized callers; authorized admins may receive a bounded conflict reason if PO approves. Never expose whether a token exists via distinct activation error messages.
- `GET /activate/[token]` is a frontend page, not a backend token validation endpoint. The page shows a password form without leaking token to analytics, error telemetry, or external URLs. On successful activation, navigate to `/login`.
- **Password policy G1 proposal:** Django configured validators, minimum **12 characters**, no common/entirely numeric/too-similar-to-email passwords; confirm exact validators and localization of messages.
- **Re-invitation policy G1 proposal:** only active App Admin can reissue for an existing pending account; previous tokens revoked atomically; no reactivation of an already active/deactivated account.

## 6. Audit integration and dependency gate

IC-008 G1 design is approved, but **implementation is not authorized**. IC-006 must not be integrated or marked Task Verified until the required audit service is implemented and available in the F-02 feature branch under its own approved task gate. Use approved controlled event vocabulary, e.g. `account.invite_created`, `account.activation_succeeded`, `account.activation_denied`, with immutable actor IDs where available and no token/email/password in audit fields. Invitation creation and successful activation must fail closed if audit persistence fails; denied attempts may be best-effort, bounded, and sanitized. No authorization is implied for implementing IC-008 by drafting IC-006.

## 7. Draft acceptance criteria and test matrix

| ID | Acceptance criterion | Required evidence |
| --- | --- | --- |
| IC-006-AC-01 | Anonymous, inactive, and non-App-Admin users cannot invite; IT role alone never grants invite permission | Parameterized API 401/403/CSRF matrix |
| IC-006-AC-02 | No self-registration route or public account creation bypass exists | URL inventory and negative API tests |
| IC-006-AC-03 | Invitation creates exactly one pending inactive user with unusable password and digest-only secret | Database assertions, secret-sentinel scan |
| IC-006-AC-04 | Only an unexpired, unconsumed, nonrevoked token activates the intended account once | Valid/expired/reused/revoked/unknown token tests |
| IC-006-AC-05 | Concurrent activation attempts cannot both succeed | Transactional concurrency test on native MySQL |
| IC-006-AC-06 | Weak initial passwords are rejected; accepted passwords use configured Django hashing and validators | Password validator and API tests |
| IC-006-AC-07 | Invalid activation errors are generic; no token/user enumeration through status/body/logs | Response equivalence and captured logs |
| IC-006-AC-08 | Invitation secret is delivered only via approved local development-safe sink; not in API responses or logs | Delivery adapter and log capture tests |
| IC-006-AC-09 | Re-invitation invalidates old tokens; existing active/deactivated users cannot be silently reactivated | Lifecycle edge-case tests |
| IC-006-AC-10 | Invitation and activation success events are audited atomically and sanitized; failure semantics follow IC-008 | Audit event and injected failure tests |
| IC-006-AC-11 | Activation UI, CSRF, login redirect and session protections function without introducing auto-login | Browser/API flow and regressions |
| IC-006-AC-12 | Four living docs and native MySQL migration, integration and regression evidence recorded for SOL review | Exact commands, output, test count, environment, PR head |

## 8. Open G1 Product Owner decisions

1. **Invitation expiry:** approve 24 hours or specify another duration.
2. **Password policy:** approve minimum 12 characters plus Django validators or revise.
3. **Admin elevation:** allow an existing App Admin to invite another App Admin during IC-006, or defer that ability to IC-007.
4. **Local delivery:** approve a restricted local file/mailbox sink accessible only to the developer, never standard application logs.
5. **Duplicate handling:** approve generic conflict for active accounts, explicit pending-account re-invite by App Admin, and no reactivation of deactivated accounts.
6. **Activation UX:** approve no automatic login and redirection to existing login page.
7. **API contract:** approve proposed route shapes/status codes or request revisions.

## 9. TTDM gates

- **G0:** F-02 scope IC-006, IC-007, IC-008 approved; IC-024 deferred pending IC-023.
- **G1:** IC-006 is **draft only**; no PO approval of this task specification yet.
- **G2/G3:** Not started; no implementation task branch, task PR, or SOL review.
- **Implementation:** **Not authorized.** This documentation PR does not grant authority for code, migrations, runtime changes, or task merges.
- **Documentation merge:** Requires separate Product Owner approval of exact PR head after SOL documentation review.
