# IC-002 test results

**Status:** Task-branch verification complete; SOL review pending  
**Environment:** Codex Windows sandbox, Python 3.13.5; not the Product Owner's
confirmed native MySQL installation.

## Actual results — 2026-10-27

| Check | Result |
| --- | --- |
| `python manage.py check --settings=config.settings.test` | Passed, no issues |
| Migration plan inspection | Only `contenttypes.0001_initial` and `0002_remove_content_type_name`; no auth/user/admin/session migrations |
| First isolated migration run | Passed; both content-types migrations applied |
| Second identical migration run | Passed; `No migrations to apply` |
| `python manage.py migrate --check --settings=config.settings.test` | Passed |
| `python manage.py test health --settings=config.settings.test --verbosity 2` | Passed, 6/6 tests |
| Healthy API contract | Passed with mocked reachable connection: exact HTTP 200/body asserted |
| Failed-database API contract | Passed with mocked failure and against local configuration: exact safe HTTP 503/body asserted |
| `npm run validate` | Passed structure and example-secret checks |
| MySQL service/listener probe | `MySQL80` running; TCP `127.0.0.1:3306` reachable |
| Django native MySQL connectivity | **Not passed:** server rejected placeholder `it_copilot` credentials with MySQL error 1045 |

Verification used Python 3.13.5, Django 5.2.7, DRF 3.16.1, and mysqlclient
2.2.7 in the Codex Windows sandbox. The migration repeatability check used an
isolated SQLite file solely to exercise Django's migration graph and idempotent
second run; it is not evidence of MySQL schema compatibility.

No Product Owner database credentials were available, so migrations were not
applied to the Product Owner's MySQL database and native MySQL connectivity is
explicitly **unverified**. The service/listener observation and predictable 503
behavior are not claimed as a successful database connectivity test.
