# IC-002 — Django/MySQL Core and Health API

**Project:** IT Support Copilot V1.0 MVP  
**Method:** TTDM-WA-001 — feature-based development  
**Feature:** F-01 Core Platform  
**Proposed task branch:** `task/IC-002-django-mysql-core` (not created)  
**Status:** Draft specification — awaiting Product Owner approval to implement  
**Priority:** P0  
**Scope authorization:** F-01 scope approved 2026-10-27; **IC-002 implementation is not authorized**.

## Objective

Initialize the Django/DRF backend inside `apps/api`, connect it to the local MySQL service established by IC-001, and expose a minimal versioned health API that supports repeatable local development and testing. Preserve existing monorepo boundaries.

## Baseline and dependencies

- IC-001 merged repository scaffold and local Compose MySQL service.
- Approved stack: Python 3.12 or 3.13, Django, Django REST Framework, MySQL, Docker Compose for local development.
- `apps/web`, `workers/document_processor`, `packages/api-contract`, and `tests/e2e` are existing ownership boundaries, not runtime services.
- The detailed API contract below is **proposed for approval**, not an existing product requirement or implemented endpoint.

## Proposed implementation scope

1. Initialize a reproducible Django project and minimal settings structure under `apps/api`; document Python version, pinned dependency strategy, and local commands.
2. Configure database connectivity via environment variables to the existing local MySQL service; never commit real secrets.
3. Add DRF and an API route namespace (proposed `/api/v1/`).
4. Add a liveness endpoint (proposed `GET /api/v1/health/live/`) returning HTTP 200 with a minimal machine-readable status when the API process is running.
5. Add a readiness endpoint (proposed `GET /api/v1/health/ready/`) that checks MySQL connectivity and returns HTTP 200 when available or HTTP 503 when unavailable, without exposing credentials or internals.
6. Support initial Django migrations for framework-owned tables and a documented fresh-database initialization.
7. Provide automated tests for liveness, readiness (database available/unavailable), settings safety, and basic startup; document any environment-dependent test constraints.
8. Update the root setup instructions, relevant architecture/API docs, and all four IC-002 TTDM records as implementation proceeds.
9. Keep local development only; avoid AWS, deployment pipelines, hosting, and production infrastructure.

## Proposed acceptance criteria

| ID | Criterion | Required evidence |
| --- | --- | --- |
| IC-002-AC-01 | Django project starts from documented local setup using supported Python and pinned dependencies. | Fresh-setup commands and captured result |
| IC-002-AC-02 | Django/DRF settings use environment-supplied secret and MySQL credentials; no real secrets committed. | Settings review, ignore checks |
| IC-002-AC-03 | Local Django connects to IC-001 MySQL Compose service with documented host/port behavior. | Connectivity and migration output |
| IC-002-AC-04 | `GET /api/v1/health/live/` returns 200 and minimal JSON when Django is running. | API test |
| IC-002-AC-05 | `GET /api/v1/health/ready/` returns 200 with MySQL reachable and 503 when unreachable, without leaking details. | Positive and negative tests |
| IC-002-AC-06 | Fresh-database migrations complete; rerunning migrations is safe. | Migration test/log |
| IC-002-AC-07 | Automated tests and applicable static/configuration checks pass; exceptions are explicitly documented. | Commands, tool versions, results |
| IC-002-AC-08 | README and API/architecture documentation reflect implemented behavior only. | Documentation review |
| IC-002-AC-09 | Diff stays within backend foundation and related local configuration/documentation; later tasks remain untouched. | PR diff review |
| IC-002-AC-10 | Four task records and SOL review are complete before any authorized task-to-feature merge. | TTDM records and reviewed PR SHA |

## Security and interface decisions for approval

- Health endpoints are proposed to be unauthenticated for local diagnostics, returning no environment details, database errors, stack traces, or secrets.
- Readiness failure should produce a generic error payload and HTTP 503; detailed failure information stays in local logs.
- No custom user/roles (IC-003), sessions/CSRF (IC-004), frontend/login (IC-005), document worker, retrieval, vault, or external AI work.
- No cloud, production deployment, hosting, or CI/CD work.
- Exact Django/DRF/MySQL driver versions and endpoint payload schemas must be recorded in the implementation plan before code is written and checked for compatibility.

## Proposed verification procedure

1. Start MySQL via existing Compose configuration and configure a local, ignored environment file.
2. Install backend dependencies in an isolated Python environment.
3. Run Django system checks and migrations against the local MySQL instance.
4. Run automated tests, including a simulated or controlled MySQL outage for readiness behavior.
5. Call both health endpoints and capture HTTP status and sanitized response bodies.
6. Repeat from a clean checkout and record OS, Python, Django, DRF, MySQL, Docker Compose, and commands actually used.

## TTDM delivery and authorization gate

The Product Owner must approve this specification **before** implementation. Upon approval, a separate `task/IC-002-django-mysql-core` branch may be created from `feature/core-platform`. Codex/Cursor supplies code, tests, and the four living documents; SOL reviews acceptance evidence and authorizes a task PR merge into the feature branch. The Product Owner separately authorizes the eventual F-01 merge into `main`.

**Not authorized by this draft:** implementation, task PR creation/merge, feature release, or changes to `main`.
