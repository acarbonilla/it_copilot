# IC-006 test results

**Status:** Local verification complete; SOL G2 exact-head review pending
**Date:** 2026-10-28
**Environment:** Windows, Asia/Singapore; Python 3.13.5; Django 5.2.7; native Windows `MySQL80`; Node/Next.js 16.4.3; SQLite in-memory where stated

## Passing commands

Commands were run from `apps/api`, `apps/web`, or the repository root as appropriate.

| Command | Environment | Result |
| --- | --- | --- |
| `.venv Python manage.py check --settings=config.settings.test` | SQLite settings | Passed, no issues |
| `.venv Python manage.py makemigrations --check --dry-run --settings=config.settings.test` | SQLite settings | Passed, no changes detected |
| `.venv Python manage.py test accounts security_audit session_auth health --settings=config.settings.test -v 1` | SQLite | Final backend regression passed 93/93 in 76.115s; 11 native-only cases skipped |
| `.venv Python manage.py check --database default --settings=config.settings.local` | Native MySQL | Passed, no issues |
| `.venv Python manage.py showmigrations accounts security_audit --plan --settings=config.settings.local` | Native MySQL | Showed both IC-006 migrations unapplied before first migration |
| `.venv Python manage.py migrate --settings=config.settings.local` | Native MySQL | Applied `accounts.0002_account_invitation` and `security_audit.0002_ic006_event_vocabulary` |
| same native migrate command, second run | Native MySQL | Passed, `No migrations to apply` |
| `.venv Python manage.py migrate --check --settings=config.settings.local` | Native MySQL | Passed, exit 0 |
| `.venv Python manage.py test accounts.tests.test_invitations --settings=config.settings.local -v 1` | Native MySQL | Final service/failure/concurrency suite passed 21/21 in 41.068s |
| `.venv Python manage.py test ...NativeConcurrentActivationTests.test_two_concurrent_activation_attempts_cannot_both_succeed --settings=config.settings.local -v 2` | Native MySQL | Passed 1/1 in 2.552s; exactly one of two threads activated |
| `npm test -- --reporter=verbose` | jsdom | Passed 23/23 tests across 5 files |
| `npm run typecheck` | TypeScript | Passed |
| `npm run lint` | ESLint | Passed with zero warnings |
| `npm run build` | Next.js production | Passed; `/activate/[token]` built as a dynamic route |
| live `Invoke-WebRequest` against `next start` activation route | Next.js production server | HTTP 200; `Referrer-Policy: no-referrer`; no external asset URL found |
| `npm run validate` | Repository | Passed structure and `.env.example` checks |
| `git diff --check` | Repository | Passed |

## Acceptance-criteria evidence

| Criterion | Evidence |
| --- | --- |
| AC-01 | API matrix proves anonymous/inactive/unknown-role/non-App-Admin/IT-admin denial, active App Admin success, and CSRF enforcement. |
| AC-02 | Route inventory allows only invitation and activation additions; `/users`, `/register`, and `/signup` POSTs return structured 404. |
| AC-03 | Service asserts one canonical pending inactive user, unusable password, UUID invitation, digest-only database value, 24-hour expiry, and bounded response. |
| AC-04 | Valid token activates once; expired, revoked, reused, unknown, and malformed values receive identical invalid responses. |
| AC-05 | Native MySQL two-thread test uses row locks and proves exactly one activation succeeds. |
| AC-06 | Short, common, numeric-only, and email-similar passwords are rejected; accepted password is Django-hashed. |
| AC-07 | Invalid-state bodies/statuses are identical; captured request/application logs do not contain the sentinel token. |
| AC-08 | File delivery requires explicit DEBUG/local configuration; response/log tests exclude the secret; disabled/partial-write failures roll back and clean artifacts. |
| AC-09 | Reissue revokes the old token atomically and updates pending grants; active and nonpending inactive accounts conflict. |
| AC-10 | Invitation and activation events are asserted; injected audit failures roll back user/password/invitation state; denial audit is sanitized. |
| AC-11 | API CSRF/session regressions pass; frontend tests cover safe token rendering, password form, API call and login replacement; no session is created. |
| AC-12 | Forward migrations pass native MySQL first/second/check flows; four living documents and architecture reference are maintained. |

## Failures encountered

1. The first accounts run failed three assertions: an expiry delta differed by microseconds, `passwordpassword` was not in Django's bundled common-password list, and the API used the same accepted value. The timestamp assertion now has a one-second tolerance and the verified common value is `password12345`; focused and full reruns passed.
2. The first complete backend regression failed the deliberate URL inventory guardrail because it did not yet include the two authorized routes. The expected set was updated with only `/api/v1/auth/activate` and `/api/v1/users/invitations`; the focused guardrail and complete rerun passed.
3. An initial chained frontend command outlived the wrapper's capture interval and is not claimed as evidence. Test, typecheck, lint, and build were rerun with complete captured output.

## Security observations and limitations

- The local mailbox necessarily contains the raw activation URL. It is ignored by Git and disabled by default, but Windows confidentiality depends on host ACLs and operator cleanup.
- Token-bearing frontend paths could be captured by infrastructure access logging in a future deployment. Hosted deployment is excluded; any future hosting task must redact these paths. The implemented page sets `no-referrer` and uses no third-party resources.
- The development file sink is not an external mail transport and has no delivery retry queue.
- Existing inactive legacy accounts migrate as lifecycle `ACTIVE` and are deliberately not invitation-eligible. IC-007 may refine lifecycle representation under its own authorization.
- No CI evidence was available; results are local. Retention, audit viewing, and deletion remain outside scope.
