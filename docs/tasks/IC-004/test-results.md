# IC-004 test results

**Status:** Task-branch verification complete; SOL review pending
**Environment:** Windows native MySQL 8.0, Python 3.13.5, Django 5.2.7

## Pre-migration inventory

- Native migrations: 15 expected IC-003 records (`accounts`, `auth`, and
  `contenttypes` only).
- Native tables: custom user/auth/contenttypes tables; no `django_session`.
- Existing native users: zero.
- Sessions graph: `sessions.0001_initial`, no dependencies, creates only the
  framework session model/table.

## Migration results

- Fresh isolated migration: passed; `django_session` and `accounts_user`
  present, `auth_user` absent.
- Second isolated migration: passed; `No migrations to apply`.
- Private ignored native pre-migration dump: passed (11,123 bytes).
- Native migration: applied only `sessions.0001_initial`.
- Second native migration: passed; `No migrations to apply`.
- Native `migrate --check`: passed; existing user count remained zero.

## Cookie-aware HTTP verification

PowerShell `WebRequestSession` was run against the real Django development
server at `http://localhost:8000` and native MySQL, with Origin
`http://localhost:3000`:

- CSRF bootstrap `200`; login `200`; authenticated `/me` `200`.
- CSRF was refreshed after login because Django rotates the CSRF secret.
- Logout `204`; replay of the captured old session cookie received `401`.
- CORS echoed only the approved origin and allowed credentials.
- CSRF cookie: `SameSite=Lax`, browser-readable; session cookie:
  `SameSite=Lax`, `HttpOnly`.
- A deliberate stale pre-login CSRF token was rejected on logout with the safe
  structured `403`, confirming rotation behavior.
- Temporary user and all test session rows were removed after verification.

## Final automated and regression results

| Check | Result |
| --- | --- |
| Django test-settings system check | Passed, no issues |
| `test session_auth accounts health` | Passed, 43/43 tests |
| Login, invalid/nonexistent/blank/inactive credentials | Passed |
| Session creation and identifier rotation | Passed |
| Authenticated and anonymous `/auth/me` | Passed |
| Logout and old-cookie replay denial | Passed |
| Missing/invalid CSRF on login and logout | Passed with structured JSON 403 |
| Disallowed Origin and unsafe HTTPS Referer | Passed; rejected with JSON 403 |
| Local and secure-context cookie flags | Passed |
| Immediate post-login deactivation denial | Passed; historical row retained per scope |
| IC-003 user, role, ownership, and migration regressions | Passed |
| IC-002 health/error/renderer/timeout regressions | Passed |
| `makemigrations --check --dry-run` | Passed; no model drift |
| Isolated and native `migrate --check` | Passed |
| Native Django database check | Passed |
| Live native health check | Passed; HTTP 200, `application/json`, `{"status":"ok"}` |
| `npm run validate` | Passed |
| `git diff --check` | Passed |

An unlabeled `manage.py test` invocation from the monorepo root discovered zero
tests and is not counted as evidence. The explicit app-label command above is
the recorded complete Django suite.
