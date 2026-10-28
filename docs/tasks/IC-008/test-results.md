# IC-008 test results

**Status:** Verification complete with one documented environment failure; SOL review pending
**Date:** 2026-10-28
**Environment:** Windows, Asia/Singapore; Python 3.13.5; Django 5.2.7; native Windows `MySQL80` service; SQLite in-memory test settings where stated

## Executed passing commands

From `apps/api` unless noted:

| Command | Environment | Result |
| --- | --- | --- |
| `python manage.py check --settings=config.settings.test` | SQLite settings | Passed, no issues |
| `python manage.py makemigrations --check --dry-run --settings=config.settings.test` | SQLite settings | Passed, no changes detected |
| `python manage.py test security_audit --settings=config.settings.test -v 1` (twice) | SQLite | Passed 12/12 twice before the final transaction-guard test was added |
| `python manage.py test accounts --settings=config.settings.test -v 1` | SQLite | Passed 19/19 |
| `python manage.py test session_auth --settings=config.settings.test -v 1` | SQLite | Passed 16/16 |
| `python manage.py test health --settings=config.settings.test -v 1` | SQLite | Passed 10/10 |
| `.venv Python manage.py test security_audit accounts session_auth health --settings=config.settings.test -v 1` | SQLite | Final combined regression passed 58/58 in 45.833s |
| `.venv Python manage.py check --database default --settings=config.settings.local` | Native MySQL | Passed, no issues |
| `.venv Python manage.py showmigrations security_audit --plan --settings=config.settings.local` | Native MySQL | Showed unapplied `security_audit.0001_initial` before migration |
| `.venv Python manage.py migrate security_audit --settings=config.settings.local` | Native MySQL | Applied `security_audit.0001_initial` successfully |
| same native migrate command, second run | Native MySQL | Passed, no migrations to apply |
| `.venv Python manage.py migrate --check --settings=config.settings.local` | Native MySQL | Passed, exit 0 |
| `.venv Python manage.py test security_audit --settings=config.settings.local -v 1` | Native MySQL | Final suite passed 13/13; test database created and destroyed |
| `npm run validate` | Repository root | Passed structure and `.env.example` checks |
| `git diff --check` | Repository root | Passed |

## Acceptance evidence

| Criterion | Evidence |
| --- | --- |
| AC-01 | Model/service and native migration tests assert action, actor snapshot, target, outcome, and timestamp persistence. |
| AC-02 | Keyword allowlist rejects forbidden fields; constrained identifiers reject free text/email-like values; captured logs exclude sentinel values. |
| AC-03 | Reusable matrix defaults deny anonymous, inactive, unknown-role, and cross-owner subjects. |
| AC-04 | App Admin alone receives no IT-document or cross-owner private-resource permission. |
| AC-05 | Existing session-auth 16/16 suite verifies 401/403, CSRF, sessions, cookies, CORS, and safe error conventions. |
| AC-06 | Audit suite passed repeated isolated runs; native migration was idempotent; model drift check passed. |
| AC-07 | Failure injection proves audit failure rolls back a real account mutation; transaction guard and single-attempt denial behavior are tested. |
| AC-08 | Route file and auth handlers are unchanged; repository validation and review found no lifecycle/deletion/viewing/retention additions. |
| AC-09 | Four task documents and data-model reference are present; native MySQL migration and 13/13 test evidence recorded. |

## Failures encountered

1. The first Django check failed with `NameError: Action is not defined` because a nested `Meta` class referenced a sibling enum. Controlled values were moved to module constants; subsequent checks passed.
2. The first audit matrix run failed 2 of 12 cases because the test incorrectly expected an unknown role to retain owner access. The expected result was corrected to default deny; repeated suites passed.
3. Native commands invoked with the global Python failed before Django connected because global Python lacked `mysqlclient` (`ModuleNotFoundError: MySQLdb`). No migration was attempted by those failed commands. The repository `.venv` contained locked `mysqlclient==2.2.7`; all native commands then passed using that interpreter.
4. One combined regression invocation outlived the command wrapper's 30-second capture window. Each app suite was rerun separately with complete final output; only those completed commands are claimed above.

## Limitations

- No CI run was available during local verification.
- No numerical retention period is approved; cleanup remains unimplemented.
- Future IC-006/IC-007 code must integrate the service in its own authorized tasks and prove transaction placement there.
