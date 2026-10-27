# IC-002 — Django/MySQL Core and Health API

**Project:** IT Support Copilot V1.0 MVP  
**Method:** TTDM-WA-001 — feature-based development  
**Feature:** F-01 Core Platform  
**Proposed task branch:** `task/IC-002-django-mysql-core` (**not created**)  
**Status:** Technical decisions finalized — awaiting separate Product Owner implementation authorization  
**Priority:** P0  
**Scope authorization:** F-01 scope approved 2026-10-27; **IC-002 implementation is not authorized**.

## Authoritative Product Owner baseline

The original IC-002 task definition governs this specification:

> **Objective:** Create the backend foundation and persistent relational schema.
>
> **Implementation scope:** Configure Django, DRF, MySQL connection, settings separation, structured JSON errors, `/api/v1/health` endpoint, migration tooling.
>
> **Acceptance criteria:** Health endpoint returns expected status; database migrations run twice safely; connection failure is handled predictably.
>
> **Verification:** Django system checks, migration tests, API health test, database connectivity test.
>
> **Dependencies:** IC-001. **Risk:** Initial migration design must precede domain model changes.

The details below operationalize this baseline; they do not replace it. Any change to the endpoint path or functional scope requires separate Product Owner approval.

## Objective and boundaries

Initialize the Django/DRF backend in `apps/api`, connect it to the IC-001 local MySQL service, establish an initial persistent relational schema through Django migration tooling, and provide the single required `/api/v1/health` endpoint with predictable failure behavior. Preserve the existing monorepo ownership boundaries.

**In scope:**
1. Reproducible Django and Django REST Framework initialization, dependency/version documentation, and startup commands.
2. **Settings separation:** explicit common/base settings and local-development settings, with environment-based secrets and database configuration; document selection and safe defaults. Do not commit real secrets.
3. **MySQL connection:** use IC-001 local Compose configuration; document hostname and port differences between host-run Django and container networking where applicable.
4. **Structured JSON errors:** define and apply a consistent machine-readable error envelope to IC-002 API failures; ensure no database exception, credential, traceback, or internal connection detail is exposed.
5. **One health endpoint:** `GET /api/v1/health` (exact path; no replacement with split liveness/readiness endpoints). Define the expected healthy and database-unavailable status codes and JSON responses in the implementation plan and test them.
6. **Initial schema and migration design:** document framework-owned tables, any IC-002-owned schema, and migration order *before* domain model changes. Do not introduce later-task domain models or preempt IC-003's custom user model design. Record any implications of Django's initial auth migrations for IC-003 and obtain a design decision before migrations that would constrain the custom user model.
7. Migration tooling, clean database initialization, and safe repeat execution of the migration command.
8. Django system checks, migration tests, API health test, database connectivity test, and documented reproducible local verification.
9. Documentation and the four TTDM task records during a later, separately authorized implementation.

**Out of scope:** custom user/roles (IC-003), session auth/CSRF (IC-004), Next.js shell/login (IC-005), document processing, Copilot, vault, cloud hosting, deployment, and CI/CD.

## Finalized API and structured error contract

The endpoint path is fixed by the Product Owner baseline: **`/api/v1/health`**. The baseline does not prescribe exact HTTP status codes, JSON fields, or a database outage response body. The following contract is the specification decision for implementation and testing:

| Condition | HTTP status | JSON body |
| --- | --- | --- |
| Django responding and MySQL reachable | `200` | `{"status":"ok"}` |
| MySQL unreachable or connectivity check fails | `503` | `{"error":{"code":"database_unavailable","message":"Service temporarily unavailable"}}` |

For other IC-002 API errors, use the same envelope: `{"error":{"code":"stable_machine_code","message":"Safe human-readable description"}}`. These response bodies and status codes are finalized for this specification. The database check must have a finite, documented timeout; the implementation agent will choose and document the exact limit for SOL review.

Health access is unauthenticated **for local development only**, with no internal diagnostic information returned. Use a bounded, read-only connectivity check so failures are predictable; no production exposure is authorized. The health endpoint must not create or mutate database records.

## Finalized initial schema and migration design decision

Before any database migration is applied, record the initial table inventory, dependency graph, and migration sequence. **Do not apply Django's default auth/user migrations in IC-002 in a way that locks in the default User model.** IC-003 owns the custom user model, which must be established in its app's initial migration before the first auth-related migration in any shared or persistent development database. IC-002 must demonstrate repeatable migration execution on a compatible clean database without preempting IC-003; if this cannot be achieved without auth migrations, stop and escalate the sequencing decision to the Product Owner rather than silently using the default User model. No IC-003 user/role code is authorized as part of IC-002.

## Acceptance criteria — original requirements preserved and made testable

| ID | Acceptance criterion | Evidence |
| --- | --- | --- |
| IC-002-AC-01 | Django and DRF initialize and run using documented supported Python and pinned dependency versions. | Startup and fresh-setup commands/results |
| IC-002-AC-02 | Settings separation is explicit and working; secrets and MySQL credentials are environment-supplied and ignored by version control. | Settings inspection and safety tests |
| IC-002-AC-03 | Django connects to local MySQL using documented configuration and can persist the initial relational schema. | Database connectivity and schema/migration evidence |
| IC-002-AC-04 | The **single** `GET /api/v1/health` endpoint returns the documented expected healthy status and JSON body. | API health test |
| IC-002-AC-05 | Database connection failure is handled predictably by the health API with documented status and **structured JSON error**, without leaking sensitive internals. | Database-down API and error-schema tests |
| IC-002-AC-06 | Initial migration design is documented **before domain model changes**; migrations run successfully on a fresh database and can be executed a second time safely. | Design record, first and second migration runs |
| IC-002-AC-07 | Django system checks, migration tests, API health test, and database connectivity test pass, or limitations are explicitly documented and not accepted as passing. | Commands, versions, actual results |
| IC-002-AC-08 | README, architecture/API docs, and migration instructions reflect implemented behavior only. | Documentation review |
| IC-002-AC-09 | Diff is limited to IC-002 backend foundation, initial schema, local configuration, tests, and documentation; no later-task features. | PR diff review |
| IC-002-AC-10 | All four IC-002 TTDM task records and SOL review are complete before any separately authorized task integration into `feature/core-platform`. | Task records and reviewed PR SHA |

## Required verification plan

1. Run Django system checks with the documented settings configuration.
2. Start IC-001 MySQL Compose service and verify database connectivity.
3. Review initial schema/migration design and confirm it does not preempt IC-003's custom user model; record the decision before applying initial migrations.
4. Apply migrations on a fresh database; run the same migration command again and verify no unsafe changes or errors.
5. Test `GET /api/v1/health` with MySQL available and unavailable, including HTTP statuses and JSON schemas.
6. Test structured JSON error responses and verify sensitive error details are absent.
7. Capture the actual command outputs, tool versions, and clean-checkout instructions. Do not claim tests pass until executed.

## Risks and controls

- **Migration ordering:** Design initial migrations before domain model changes. Django's user model is especially sensitive to initial migration choices; IC-003's custom user model must not be made unnecessarily difficult by IC-002.
- **Connectivity failures:** Use a bounded check and safe JSON error; do not expose secrets or internal exceptions.
- **Configuration drift:** Keep settings separation and environment variable selection explicit.
- **Scope drift:** Do not introduce split health endpoints or later-task functionality without Product Owner approval.

## TTDM authorization gate

The Product Owner approved the **F-01 scope**, not IC-002 implementation. This document is a **specification revision only** on `feature/core-platform`. No IC-002 task branch, code, PR, task integration, or F-01 release is authorized.

The health HTTP/JSON contract and migration design guardrail are finalized in this specification. **Separate explicit Product Owner authorization is still required before implementation or task branch creation.** Only then may a task branch be created for a separately authorized Codex/Cursor handoff. SOL reviews implementation evidence and authorizes task-to-feature integration under TTDM-WA-001; the Product Owner separately approves any F-01 merge into `main`.
