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
| `python manage.py test health --settings=config.settings.test --verbosity 2` | Passed, 10/10 tests after IC-002-REV-01 |
| Healthy API contract | Passed with mocked reachable connection: exact HTTP 200/body asserted |
| Failed-database API contract | Passed with mocked failure and against local configuration: exact safe HTTP 503/body asserted |
| `npm run validate` | Passed structure and example-secret checks |
| MySQL service/listener probe | `MySQL80` running; TCP `127.0.0.1:3306` reachable |
| Django native MySQL connectivity | Passed with the Product Owner-configured non-root account; database system check and `SELECT 1` succeeded |
| Native MySQL migration plan | Only `contenttypes.0001_initial` and `0002_remove_content_type_name`; no auth/user/admin/session migrations |
| Native MySQL first migration run | Passed; both content-types migrations applied |
| Native MySQL second migration run | Passed; `No migrations to apply` |
| Native MySQL health request | Passed; HTTP 200 with exact body `{"status":"ok"}` |
| JSON-only rendering regression | Passed; `Accept: text/html` returned structured JSON 406 and no template exception |
| Timeout configuration | Passed; native settings reported positive `(connect, read, write)` timeouts of `(5, 5, 5)` seconds |
| Simulated stalled-read failure | Passed; mocked `OperationalError` returned exact safe HTTP 503 body without exception text or credentials |
| Live unavailable-connection behavior | Passed; invalid local port returned exact safe JSON 503 in 3.24 seconds |
| Post-correction native MySQL check | Passed; database system check, `SELECT 1`, and HTTP 200 health response |
| Post-correction native migration repeatability | Passed; two consecutive runs each reported `No migrations to apply`; `migrate --check` passed |
| Post-correction `npm run validate` | Passed structure and example-secret checks |

Verification used Python 3.13.5, Django 5.2.7, DRF 3.16.1, and mysqlclient
2.2.7 in the Codex Windows sandbox. The migration repeatability check used an
isolated SQLite file solely to exercise Django's migration graph and idempotent
second run; it is not evidence of MySQL schema compatibility.

After the Product Owner supplied the private `.env` configuration, the native
MySQL checks above were executed successfully on 2026-10-27. Credentials were
not printed or committed. The earlier isolated SQLite run remains useful as an
independent migration-graph/idempotency check; native MySQL results are now
recorded separately above.

## IC-002-REV-01 limitations

The automated suite simulates a driver read timeout and verifies the exact safe
response. A deliberate stall of the Product Owner's running MySQL service was
not induced because doing so could disrupt unrelated local work. The native
driver configuration and connection-failure deadline were verified directly;
the read-timeout failure path was verified through controlled mocking.
