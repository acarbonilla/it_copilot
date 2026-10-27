# IC-002 implementation

**Status:** In Review
**Branch:** `task/IC-002-django-mysql-core`  
**Target:** `feature/core-platform`  
**Authorization:** Product Owner request, 2026-10-27
**Pull request:** [#5](https://github.com/acarbonilla/it_copilot/pull/5)

## Implemented scope

- Django 5.2.7, Django REST Framework 3.16.1, mysqlclient 2.2.7, and python-dotenv 1.1.1 are pinned.
- Base, local-MySQL, and isolated-test settings are separated; credentials come from the ignored `.env`.
- Native Windows MySQL is primary; Compose stays optional.
- The sole route is `GET /api/v1/health`, using bounded, read-only `SELECT 1`.
- API errors use a stable JSON envelope without internal details.
- Auth/admin/session apps are excluded to preserve IC-003's custom-user migration.

## Migration sequence

The pre-migration inventory and dependency decision are recorded in
`docs/architecture/data-model.md`. IC-002 applies only content-types migrations
and Django migration bookkeeping. IC-003 must define the custom user in its
initial migration before auth is enabled.

## IC-002-REV-01 corrections

SOL review identified two blocking reliability findings. DRF is now restricted
globally to `JSONRenderer`, so an `Accept: text/html` request receives a JSON
`406` response rather than invoking the browsable API template renderer.

Native MySQL options now enforce positive finite connection, read, and write
timeouts. Each defaults to five seconds and is configurable through
`MYSQL_CONNECT_TIMEOUT`, `MYSQL_READ_TIMEOUT`, and `MYSQL_WRITE_TIMEOUT`.
Database connection/read failures remain contained by the health view and
return only the approved safe `503` contract.

The task index was also corrected to record IC-001 PR #2 as closed without
merge and PR #4 as the merged documentation closeout.
