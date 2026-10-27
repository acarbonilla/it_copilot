# IC-002 implementation

**Status:** In Progress  
**Branch:** `task/IC-002-django-mysql-core`  
**Target:** `feature/core-platform`  
**Authorization:** Product Owner request, 2026-10-27

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
