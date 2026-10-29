# IC-007 — Test Results

**Environment:** Windows 11 / PowerShell; Django 5.2.7; native MySQL; Next.js 16.4.3
**Date:** 2026-10-28

| Command | Result |
| --- | --- |
| `python manage.py check` | PASS, 0 issues |
| `python manage.py makemigrations --check --dry-run` | PASS, no changes |
| `python manage.py migrate` | PASS; both IC-007 `0003` migrations applied on native MySQL |
| `python manage.py showmigrations accounts security_audit` | PASS; all through `0003` applied |
| `python manage.py test accounts.tests.test_lifecycle -v 1` | PASS, 15 tests in 47.523 seconds on native MySQL |
| `python manage.py test accounts.tests.test_invitations accounts.tests.test_invitation_api -v 1` | PASS, 32 tests in 59.492 seconds on native MySQL |
| `python manage.py test -v 1` | PASS, final rerun 112 tests in 166.471 seconds on native MySQL |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS, zero warnings |
| `npm test -- --run` | PASS, 6 files / 27 tests |
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

Repository `npm run validate` passed (19 required paths and secret-pattern check), and final `git diff --check` passed. The native MySQL database reported no migrations to apply, all accounts/security-audit migrations through `0003` applied, and no model drift. One combined validation invocation from the repository root used the API-relative `..\..\.venv` path and failed to locate Python; the same Django commands were rerun from `apps/api` and passed as recorded above.

## G2 remediation evidence

- G2-01: native concurrent downgrade/downgrade and reactivation/deactivation tests join the existing deactivation/deactivation race. Pending activation also uses the shared protocol. All membership transitions serialize through the singleton lock and leave at least one active activated App Admin.
- G2-02: frontend tests cover first/last disabled controls, navigation to record 21, current-page refresh after mutation, and empty results.
- G2-03: tests cover malformed inert session data, injected decode exception, injected session deletion failure, successful multi-session denial, and audit failure rollback. No test or application log emits session keys or decoded content.

Corrected during remediation: the first focused malformed-session test used a nonexistent `User.date_joined` field and was changed to `timezone.now()`; the pagination test exposed initial-load/page-load races and now uses page state plus effect cancellation. Extending the lock to invitation activation exposed Django `TransactionTestCase` flush removal of the migration seed, so an idempotent `post_migrate` receiver now restores the singleton and the 32-test IC-006 regression passed. Initial focused runs containing these failures are not reported as passes.

Original tests were executed against `0fd44e949a069be9a081f7f9b650b67094be8191`. The table above records the actual post-remediation reruns against content committed as `c252435534ad99c018b94dad1cb42e506d8dbf76`; the final documentation-only head is recorded in the draft PR and delivery report.
