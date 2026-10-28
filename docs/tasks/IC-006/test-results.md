# IC-006 test results

**Status:** G2 remediation verification complete; exact-head re-review pending
**Date:** 2026-10-28
**Environment:** Windows, Asia/Singapore; Python 3.13.5; Django 5.2.7; native Windows `MySQL80`; Node/Next.js 16.4.3; SQLite in-memory where stated
**Draft PR:** #14 targeting `feature/identity-administration`; exact final head supplied in PR and handoff

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

## SOL G2 remediation — 2026-10-28

SOL issued a conditional pass/G3 hold at reviewed head `54e55ee16ee22a628b4477867c28c5a218832806`. The remediation implementation commit is `91485fef60ef47adbb35373deef59427327d02dd`.

| Command/check | Environment | Result |
| --- | --- | --- |
| Three focused collision/partial-write/commit-failure tests | SQLite | Passed 3/3 in 3.455s |
| Four focused collision/partial-write/commit-failure/concurrency tests | Native MySQL | Passed 4/4 in 7.207s |
| Native collision test plus full `accounts.tests.test_invitations` rerun | Native MySQL | Passed focused 1/1 and final 25/25 in 44.401s |
| `manage.py test accounts security_audit session_auth health --settings=config.settings.test -v 1` | SQLite | Final regression passed 97/97 in 82.493s; 13 native-only cases skipped |
| `npm test -- --reporter=verbose` | jsdom | Passed 23/23; history test proves `/activate/<token>` becomes `/activate` after hydration |
| `npm run typecheck` / `npm run lint` / `npm run build` | Next.js 16.4.3 | Passed; build includes static `/activate` and dynamic `/activate/[token]` |
| Production `next start` response inspection with fake sentinel | Local HTTP | HTTP 200; three total token occurrences, all three in scripts; zero outside scripts/visible text; `no-referrer`; zero external asset URLs |
| `next start` output after sentinel request | Local process output | No request-path output emitted by the framework process |
| Django test/local checks, model-drift check, native `migrate --check`/`showmigrations`, `npm run validate`, `git diff --check` | SQLite/native MySQL/repository | Passed; both IC-006 migrations remain applied and no model changes were detected |

Remediation assertions:

- A forced UUID/file collision raises `FileExistsError`, preserves exact pre-existing sentinel contents, and rolls back user/invitation rows.
- A partial JSON write deletes the newly created partial artifact and rolls back the database.
- A simulated database `commit()` failure after successful artifact creation invokes rollback and removes the artifact; no user/invitation survives.
- Native MySQL repeats these failure cases and retains the two-thread single-activation guarantee.
- Actual Next.js HTML does contain the token in serialized hydration payloads. Documentation no longer claims HTML absence.

Remediation failures encountered:

1. The first full native 25-test remediation run failed two collision cases because patching Django's model-field default was order/backend dependent, despite passing focused runs. Invitation creation now uses a private UUID4 generator with a deterministic test seam; the focused and complete native reruns passed.
2. The first production server restart received `EADDRINUSE` from a prior local verification child process. The explicitly identified local Node processes were stopped, the server restarted, and the response inspection completed. This is not counted as a passing first attempt.

Residual consistency and exposure limitations:

- No distributed transaction exists across MySQL and the filesystem. Caught failures are cleaned, but sudden process/host loss can leave an orphan artifact. With no committed digest it cannot activate, yet it still contains sensitive local data.
- Filesystem loss after a successful database commit can make a valid invitation undeliverable; the local sink has no durable retry protocol.
- History scrubbing occurs after hydration. The token necessarily exists in the initial address/request, browser network tooling, serialized hydration source, and memory. Future reverse-proxy/access logging must redact activation paths before hosted use.
