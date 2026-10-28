# IC-007 — Test Results

**Environment:** Windows 11 / PowerShell; Django 5.2.7; native MySQL; Next.js 16.4.3
**Date:** 2026-10-28

| Command | Result |
| --- | --- |
| `python manage.py check` | PASS, 0 issues |
| `python manage.py makemigrations --check --dry-run` | PASS, no changes |
| `python manage.py migrate` | PASS; both IC-007 `0003` migrations applied on native MySQL |
| `python manage.py showmigrations accounts security_audit` | PASS; all through `0003` applied |
| `python manage.py test accounts.tests.test_lifecycle -v 1` | PASS, 10 tests including native MySQL concurrency |
| `python manage.py test -v 1` | PASS, 107 tests in 157.232 seconds on native MySQL |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS, zero warnings |
| `npm test -- --run` | PASS, 6 files / 25 tests |
| `npm run build` | PASS; `/admin/users` present |

## Acceptance evidence

- AC-01/03/04: negative authorization matrix, safe serialization, pagination, PATCH allowlist.
- AC-02: IC-006 invitation retained; direct POST user creation and registration remain unavailable.
- AC-05/06: multi-session revocation, subsequent denial, pending rejection, fresh login requirement.
- AC-07/08: last-admin self-action and native two-thread MySQL shared-lock race.
- AC-09: review created while user, active state, and sessions remain unchanged.
- AC-10: audit assertions and injected audit failure rollback.
- AC-11: UI authorization, list and explicit confirmation tests plus production build.
- AC-12: native migrations, drift, regressions, frontend checks, repository validation.

Corrected during implementation: DRF generic-500 assertion for injected audit failure; approved route inventory; frontend closure lint finding. The session scan and in-flight-request limitations are recorded in `implementation.md`.

Repository `npm run validate` passed (19 required paths and `.env.example` secret-pattern check). `git diff --check` passed after Markdown whitespace correction. The first full backend run found the concurrency fixture's migration seed had been removed by Django test flush; the fixture now restores the production singleton invariant, the targeted native race passed, and the subsequent 107-test full regression passed.
