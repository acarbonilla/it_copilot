# IC-006 — Account Invitation and Activation

**Status:** SOL G2 conditional pass/G3 hold at `54e55ee16ee22a628b4477867c28c5a218832806`; authorized remediation complete for exact-head re-review
**Feature:** F-02 Identity & Administration (G0 planning approved)  
**Priority:** P0  
**Dependencies:** IC-003 and IC-004 complete; IC-008 merged into `feature/identity-administration` at `726edee0312a6ad5522c1bf1aa08936477386336`
**Owner:** Codex implementation; SOL review pending
**Implementation commit:** `dfcb77c281480154ac1a7c10cd631e6e182fb16e`
**G2 remediation commit:** `91485fef60ef47adbb35373deef59427327d02dd`
**Implementation PR:** Draft PR #14 targeting `feature/identity-administration`; exact final head supplied in PR and handoff
**Updated:** 2026-10-28

## 1. Source-derived requirement

The original *IT Support Copilot V1.0 | TTDM Development Specification*, **IC-006 | Invitation and activation**, defines:
- **Objective:** Enable App Admin-provisioned accounts without self-registration.
- **Implementation scope:** Single-use hashed activation token, expiry, initial password setup, generic error behavior, development-safe email output.
- **Acceptance:** Only App Admin can invite; token single-use and expires; initial password meets policy; invitation does not disclose tokens in logs.
- **Verification:** API tests for expired/reused tokens and unauthorized invitation.
- **Dependencies:** IC-003 and IC-004. **Risk:** Token disclosure or enumeration.

The contract below originated as SOL's proposed G1 design details, not additional wording from the original specification. The Product Owner approved the seven enumerated design recommendations on 2026-10-27 and separately authorized IC-006 implementation only on 2026-10-28. The later authorization does not extend to IC-007, IC-024, or unrelated scope.

## 2. Scope and exclusion

**In scope (proposed):** Admin-only invitation initiation; pending inactive account state; one-time token issuance and validation; secure initial password setup and activation; development-only delivery adapter; audit integration contract; minimal activation frontend; repeatable security/API/browser tests and four TTDM living documents.

**Out of scope:** Public sign-up, account recovery/password reset, invitation bulk import, external email service, account lifecycle management after activation (IC-007), vault or document access grants beyond existing role policy, permanent deletion (IC-024), hosted deployment.

**Security boundaries:** `is_app_admin` is independent of `it_role`; an IT documentation administrator is not automatically an App Admin. Backend authorization is authoritative. Existing authenticated session/CSRF behavior must not regress.

## 3. Proposed workflow and state machine

1. An **active authenticated App Admin** submits an invite request for an email address and explicitly selected initial `it_role` and `is_app_admin` flag. The latter is privileged; only App Admin may grant it. **Approved G1 decision:** an active App Admin may invite another App Admin; the backend must enforce this privilege.
2. Server canonicalizes email exactly as `accounts.User` does; performs duplicate/inactive/pending-account checks without revealing account existence to unauthorized users. A unique user identity must not be duplicated.
3. Create a pending **inactive** user with an unusable password and a random activation secret. Store **only a cryptographic digest** of the secret, expiration timestamp, issuance/consumption timestamps, and reference to the intended user; never persist the raw token.
4. Generate an activation link to the local Next.js route `/activate/[token]`. The development-safe delivery adapter may show the link in a controlled local mailbox/file sink **only in explicitly configured development mode**, not application logs or production-like output. The restricted developer-only retrieval procedure must be documented before implementation; the Product Owner approved the local mailbox/file sink as the delivery design.
5. On activation submit, atomically validate digest match, not expired, not consumed, and user eligible; apply Django password validators and approved minimum password policy; set password, activate user, consume token in one transaction, and write the required audit event in that transaction.
6. Replay, expired, revoked, unknown, or malformed token attempts receive a uniform safe response. They do not activate accounts or reveal whether a user exists. A new invitation must invalidate older unconsumed tokens for that user.
7. Activation **does not automatically authenticate** the user. Redirect to login; normal IC-004 session/CSRF flow remains the only login path.

**Local token-exposure boundary:** the approved token-in-path contract means the initial browser and Next.js server request contains the token. Next.js also serializes the token as a client-component prop in the hydration script payload; it is not visible text. After hydration the client replaces the address/history URL with tokenless `/activate`, and success replaces it with `/login`. `no-referrer` and no third-party assets prevent outgoing referrer disclosure. They do not remove the initial request from browser network tooling, response source, process memory, or future proxy/access logs. This is a local-MVP trust boundary; hosted use requires separately authorized path redaction or a redesigned exchange.

**State transitions (proposed):** `NO_ACCOUNT → PENDING_INACTIVE → ACTIVE`; `PENDING_INACTIVE → EXPIRED/REVOKED → PENDING_INACTIVE` via authorized re-invite. Deactivated existing accounts must **not** be reactivated by invitation; that belongs to IC-007.

## 4. Proposed data and service design

- Existing `accounts.User` retains unique canonicalized email, `is_active`, `is_app_admin`, `it_role`, password hash. Pending invite users must have `is_active=False` and `set_unusable_password()`.
- Proposed `AccountInvitation` table: opaque primary key, user reference, token digest (unique), `created_at`, `expires_at`, `consumed_at` (nullable), `revoked_at` (nullable), `invited_by_user_id` immutable nonsecret snapshot. No raw token, email or request body in audit metadata.
- Generate token with a cryptographically secure random generator, at least 256 bits entropy; store SHA-256 digest or a suitable keyed digest, use constant-time comparisons where applicable. Never put token in analytics, exception traces, server logs or referrer-bearing outbound links.
- Expiry **approved: 24 hours** from issuance. This duration is a PO-approved G1 design detail, not a requirement stated in the original source.
- Enforce concurrency safety: consume via transaction/row locking or conditional update; two simultaneous activation attempts cannot both succeed. Account creation, invitation, and audit success event must be atomic. If critical audit persistence fails, fail closed.
- Avoid emailing secrets to external recipients in local-only MVP. Restrict delivery sink and document cleanup of development-only token artifacts.
- Database and filesystem operations are not a distributed transaction. The service owns and deletes only files it successfully created, cleans partial writes and caught commit failures, and preserves pre-existing collision files. A process/host crash between file write and database commit can leave an orphan secret file; because no digest committed, that token cannot activate, but operator cleanup remains mandatory. Filesystem loss after commit has no automatic redelivery.
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
- Invite conflicts must not reveal existing users to unauthorized callers; authorized App Admins may receive the approved bounded `invitation_conflict` response. Never expose whether a token exists via distinct activation error messages.
- `GET /activate/[token]` is a frontend page, not a backend token validation endpoint. The page shows a password form without leaking token to analytics, error telemetry, or external URLs. On successful activation, navigate to `/login`.
- **Password policy (G1 approved):** minimum **12 characters** plus configured Django password validators, including common-password, numeric-only and user-attribute similarity checks. Exact safe client error presentation remains an implementation detail to verify.
- **Re-invitation policy (G1 approved):** only an active App Admin can explicitly reissue for an existing pending account; previous tokens are revoked atomically; no silent reactivation of an already active/deactivated account.

## 6. Audit integration and dependency gate

IC-008 is implemented, reviewed, and merged into the F-02 feature branch. IC-006 adds `account.activation_succeeded`, `account.activation_denied`, and `account_invitation` through the required new forward migration `security_audit.0002_ic006_event_vocabulary`; the applied IC-008 migration is unchanged. Events use immutable actor IDs where available and contain no token, digest, email, password, or raw payload. Invitation creation and successful activation fail closed in the mutation transaction. Denials use IC-008's bounded autocommit-only recorder outside rolled-back transactions.

## 7. G1-approved acceptance criteria and test matrix

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

## 8. Product Owner G1 decision — 2026-10-27

The Product Owner **approved all seven IC-006 G1 design recommendations for specification planning only**:

1. **Token lifetime:** 24 hours.
2. **Password policy:** minimum 12 characters plus Django validators.
3. **Admin elevation:** an existing active App Admin may invite another App Admin.
4. **Development delivery:** restricted local mailbox/file sink, never application logs.
5. **Duplicate/re-invitation:** explicit pending-account re-invite; no silent reactivation.
6. **Activation UX:** redirect to existing login; no automatic authentication.
7. **API contract:** accept the proposed invitation/activation routes and response semantics in Section 5.

This was the historical G1 decision. The Product Owner subsequently authorized complete IC-006 implementation only on 2026-10-28. That later gate does not authorize IC-007 administration, IC-024 deletion, hosted deployment, audit viewing/retention, unrelated code, or any merge.

## 9. TTDM gates

- **G0:** F-02 scope IC-006, IC-007, IC-008 approved; IC-024 deferred pending IC-023.
- **G1:** The Product Owner approved the seven IC-006 design recommendations on 2026-10-27; PR #11 later merged the approved specification.
- **Implementation gate:** The Product Owner explicitly authorized IC-006 implementation only on 2026-10-28.
- **G2:** SOL issued a conditional pass/G3 hold on draft PR #14 at exact head `54e55ee16ee22a628b4477867c28c5a218832806`. The Product Owner authorized remediation of mailbox ownership, commit-failure consistency, and token-exposure findings. Remediation is complete at implementation commit `91485fef60ef47adbb35373deef59427327d02dd`; the final documentation head is supplied in PR #14 and the handoff for re-review.
- **G3:** Not started. No task or feature merge is authorized by implementation completion.
