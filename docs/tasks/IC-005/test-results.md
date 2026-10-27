# IC-005 test results

**Date:** 2026-10-27  
**Environment:** Windows, Node.js 24.13.0, npm 10.8.2, Python virtualenv,
native MySQL, Microsoft Edge, `localhost:3000` / `localhost:8000`

## Frontend verification

| Check | Actual result |
| --- | --- |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS, zero warnings |
| `npm test` | PASS, 4 files / 13 tests |
| `npm run build` | PASS; `/`, `/login`, `/dashboard` generated |
| `npm audit` | PASS, zero vulnerabilities |

Component coverage includes required fields and tab order, successful and failed
login, duplicate submission blocking, generic credential errors, distinct
network errors, anonymous redirect, identity restoration, placeholder labels,
App Admin visibility without IT-role inference, logout, and root redirects.
API-client tests verify credentialed requests, CSRF bootstrap, login rotation,
and use of the rotated token for logout.

## Real-browser E2E

Playwright drove installed Microsoft Edge against the actual Next.js development
server, Django API, and native MySQL database. Result: **1 passed in 17.4s**.

The run verified anonymous dashboard redirect, real login, credentialed CORS,
an HttpOnly session cookie, browser-readable CSRF cookie, at least two CSRF
bootstrap responses across login rotation, identity persistence after refresh,
logout, and denial after revisiting the dashboard. Server logs recorded the
expected 401, CSRF GET, CORS OPTIONS, login 200, `/me` 200, logout 204, and
post-logout 401 sequence. The temporary E2E database user was removed.

## Backend and repository regressions

- Native Django system/database check: PASS.
- Native `migrate --check`: PASS; no pending migrations.
- IC-004/IC-003/IC-002 suite: **45 passed, 0 failed** in 47.673s.
- Root `npm run validate`: PASS.
- `git diff --check`: PASS.

No Docker service was used. This was an actual local browser run, not a mocked
request or PowerShell-only HTTP check.
