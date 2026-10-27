# IC-004 implementation

**Status:** In Review
**Branch:** `task/IC-004-session-auth-csrf`  
**Target:** `feature/core-platform`  
**Authorization:** Product Owner approval of the API contract and S-01 through S-05, 2026-10-27
**Pull request:** [#7](https://github.com/acarbonilla/it_copilot/pull/7)

## Implemented scope

- Django database-backed sessions with `SessionMiddleware` and
  `AuthenticationMiddleware` using `accounts.User`.
- `GET /api/v1/auth/csrf`, `POST /api/v1/auth/login`,
  `POST /api/v1/auth/logout`, and `GET /api/v1/auth/me`.
- Django `authenticate`, `login`, and `logout`; minimal identity responses only.
- Explicit CSRF protection on anonymous login and authenticated logout, with a
  safe structured JSON CSRF failure view.
- Exact credentialed CORS origin `http://localhost:3000` for the API at
  `http://localhost:8000`; no wildcard origins.
- HttpOnly/Lax session cookies, browser-readable/Lax CSRF cookies, explicit
  local HTTP exception, and `DJANGO_COOKIE_SECURE=true` for HTTPS contexts.
- Immediate next-request denial for deactivated accounts without IC-007 bulk
  session cleanup.

## Migration safety gate

Before sessions were enabled, native MySQL contained the 15 expected IC-003
migration records, the custom user/auth/contenttypes tables, no
`django_session` table, and zero user records. `sessions.0001_initial` has no
dependencies and creates only `django_session`; it does not alter existing
account or auth migrations. The graph must pass fresh and repeated isolated
migrations before native migration is applied.

The isolated graph passed first and repeated runs. A private ignored native
backup was created, then `sessions.0001_initial` was applied to MySQL and
immediately repeated with no pending migration. Existing user count remained
unchanged.

## IC-004-REV-01 correction

`LoginView` now verifies that DRF's parsed request body implements `Mapping`
before reading fields. Valid JSON arrays, null, strings, numbers, and booleans
receive the existing structured `400 invalid_request` response. Syntactically
malformed JSON continues through DRF's structured `400 parse_error` path. CSRF
validation still runs before payload processing.
