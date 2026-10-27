# IC-004 — Session Authentication and CSRF

**Project:** IT Support Copilot V1.0 MVP  
**Feature:** F-01 Core Platform  
**Method:** TTDM-WA-001  
**Status:** Specification draft — SOL security-design proposal; Product Owner approval pending  
**Priority:** P0  
**Dependency:** IC-003 Verified and integrated via PR #6  
**Proposed task branch:** `task/IC-004-session-auth-csrf` (not created)

## Authoritative Product Owner baseline (TTDM Development Specification)

> **Objective:** Implement safe login/logout/current-user behavior.  
> **Implementation scope:** Django session authentication; login, logout and /auth/me endpoints; CSRF for state-changing requests; invalidation on deactivation.  
> **Acceptance criteria:** Valid credentials create a session; invalid credentials fail; logout revokes session; anonymous and deactivated users cannot call protected endpoints.  
> **Verification:** API login/logout/CSRF tests, browser cookie behavior, negative tests.  
> **Dependencies:** IC-003. **Risk:** Browser-origin and CSRF setup must be tested together.

Additional source requirements: Django session authentication with CSRF protection; secure cookie settings appropriate to execution context; deactivation invalidates access immediately. IC-005 owns the frontend login UI; IC-006/IC-007 own invitation, activation and account lifecycle.

## Proposed API contract — for PO approval

All paths are under `/api/v1`. Preserve IC-002 `GET /api/v1/health` unchanged.

| Endpoint | Authentication | Behavior |
| --- | --- | --- |
| `GET /api/v1/auth/csrf` | Anonymous allowed | Bootstrap a CSRF cookie/token for a browser client; no account data or session login |
| `POST /api/v1/auth/login` | Anonymous allowed, **CSRF required** | Accept email/password; on success rotate session identifier via Django login and return minimal safe current-user data |
| `POST /api/v1/auth/logout` | Authenticated, **CSRF required** | Invalidate the current server-side session; no GET logout |
| `GET /api/v1/auth/me` | Authenticated and active | Return minimal identity, App Admin flag and IT role; never password/hash or private content |

Proposed success statuses: CSRF bootstrap `200`; login `200`; logout `204`; current-user `200`. Proposed failure statuses: bad credentials `401` generic; missing/inactive session `401`; missing/invalid CSRF `403`; invalid request `400`; unsupported method `405`. Use existing structured JSON errors. These exact paths/statuses are design proposals, not verbatim source requirements.

## Proposed security decisions — require PO approval

### S-01 — Django sessions and authenticated identity

- Enable `django.contrib.sessions`, `SessionMiddleware`, `AuthenticationMiddleware`, and Django session authentication using `accounts.User` (`AUTH_USER_MODEL` from IC-003).
- Use database-backed server-side sessions; do not implement JWT, localStorage bearer tokens, self-registration or third-party identity providers.
- Login uses Django `authenticate` and `login`; logout uses Django `logout`. Successful login rotates session identifiers to prevent fixation; invalid login does not create an authenticated session.
- Protected API views check authentication **and current active status**; anonymous/inactive users are denied regardless of App Admin, IT role or Django superuser flags.
- Return only approved identity fields (e.g., ID, email, `is_app_admin`, `it_role`) in `/auth/me`. No privileged document or vault data.

### S-02 — CSRF coverage including login

- Require CSRF validation on **all** state-changing session endpoints, including anonymous `POST /auth/login` and authenticated `POST /auth/logout`. Do not rely solely on DRF `SessionAuthentication` CSRF checks because unauthenticated login requests may bypass them.
- Use Django `CsrfViewMiddleware` and explicit CSRF protection for login/logout (or equivalent verified enforcement), with a browser bootstrap `GET /auth/csrf`.
- Reject missing, invalid or cross-origin CSRF tokens and unsafe Origin/Referer as applicable. Do not exempt login, logout or future unsafe endpoints globally.
- Browser clients send the CSRF token via `X-CSRFToken` and cookies with `credentials: "include"` for an explicitly approved same-origin or local-development origin arrangement.
- Verify that CSRF failures use the project's safe structured JSON error contract, with no HTML debug output.

### S-03 — Browser origin and cookie configuration

- Default local development to same-site browser/API origins; explicitly configure allowed frontend origin(s), `CSRF_TRUSTED_ORIGINS` and CORS **only if necessary** for the selected local topology.
- Use HttpOnly session cookies, `SameSite=Lax` for same-site local development, and non-HttpOnly CSRF cookie if JS reads it. Do not store session credentials in browser localStorage.
- `Secure` cookies must be enabled in HTTPS execution contexts; local HTTP development exceptions must be explicit, environment-scoped and documented. Avoid wildcard CORS origins, `Access-Control-Allow-Origin: *` with credentials, or unrestricted trusted origins.
- Define a reproducible browser test origin pair (e.g., `http://localhost:3000` frontend and `http://localhost:8000` API); ensure consistent hostnames rather than mixing `localhost` and `127.0.0.1` in cookie tests.
- This is local Windows 10 native MySQL development only; no cloud/deployment work.

### S-04 — Deactivation and session invalidation

- A deactivated user must be denied on the **next protected request**, even when a session cookie was issued before deactivation. Django's active-user checks and an explicit view-level active guard must be tested against a fresh database read.
- Logout invalidates the current session; replaying its old session cookie must not restore access.
- Immediate rejection on deactivation is mandatory. Physical purge of **all** historical sessions for a deactivated account is an IC-007 lifecycle responsibility unless needed for the security contract; document the distinction between immediate access denial and session-row deletion.
- Session expiration and login/logout behavior must not expose credentials or internal diagnostics.

### S-05 — Endpoint contract, errors and test gates

- Keep `GET /api/v1/health` unauthenticated and unchanged; new auth routes are scoped only to IC-004.
- Enforce permissions on backend views; no reliance on frontend redirects (IC-005) or UI hiding.
- Use JSON-only DRF rendering and structured machine-readable errors consistent with IC-002. Avoid account enumeration: invalid email, wrong password and inactive account receive the same safe login error.
- Test API success/failure and negative cases: valid login, wrong password, nonexistent email, blank email, inactive account, anonymous `/me`, logout/replay, missing/invalid CSRF on login/logout, valid CSRF, disallowed Origin, browser cookie attributes, session rotation, and IC-002/IC-003 regressions.
- Verify browser cookie and CSRF behavior with an actual local browser or equivalent HTTP client that maintains cookies and origin headers; record exactly what was executed. Tests must enable CSRF enforcement explicitly, not rely only on DRF test client defaults.

## Migration and verification guardrails

1. Before applying migrations, inspect existing `django_migrations` and confirm IC-003 custom user and auth migrations are present and consistent. Preserve existing user records.
2. Review sessions migration graph and table inventory; apply only expected Django session migrations. Do not modify IC-003 `accounts.0001_initial` or rebuild existing user tables.
3. Run system checks, isolated first/repeated migrations, native MySQL migration and repeat, login/logout/CSRF negative tests, and IC-002/IC-003 regression tests.
4. Record actual browser origin, cookie behavior, CSRF trusted origins, and HTTP/HTTPS configuration without exposing secrets.
5. Maintain all four IC-004 TTDM task records, architecture/API documentation and F-01 task matrix.
6. Task implementation and task-to-feature merge require separate PO authorization and subsequent SOL review respectively. F-01 feature-to-`main` requires separate PO approval.

## Scope exclusions

- IC-005 Next.js login screen, redirects and app shell.
- IC-006 invitation, activation, initial password setup.
- IC-007 account lifecycle administration and bulk session purge.
- Document/vault models, permission enforcement in future domain services, audit subsystem.
- Production deployment, cloud services, hosting and CI/CD pipelines.

## Open approval questions

1. Approve the proposed four endpoint paths and status codes, including `GET /auth/csrf` bootstrap?
2. Approve local browser topology using `localhost:3000` and `localhost:8000` as the initial test pairing, with exact-origin configuration if required?
3. Approve S-01 through S-05 and the distinction between immediate deactivation access denial (IC-004) and bulk session-row cleanup (IC-007)?

**Current gate:** Planning draft only; do not create an IC-004 task branch, implement code, create a PR, or merge until the Product Owner explicitly approves the design and authorizes implementation.
