# IC-003 — Custom User Model and Role Policy

**Project:** IT Support Copilot V1.0 MVP  
**Feature:** F-01 Core Platform  
**Method:** TTDM-WA-001  
**Status:** Specification draft — Product Owner review required; implementation not yet authorized  
**Priority:** P0  
**Dependency:** IC-002 Verified and integrated into `feature/core-platform` via PR #5  
**Proposed task branch:** `task/IC-003-custom-user-roles` (not created)

## Authoritative Product Owner baseline

> **Objective:** Establish identity and distinct administrative/IT roles before initial migrations.  
> **Implementation scope:** Email-based custom User, active status, App Admin flag, IT role enum, backend policy helpers.  
> **Acceptance criteria:** Unique email; disabled account rejected; App Admin does not implicitly grant private-document or vault access; IT roles enforce shared-document permissions.  
> **Verification:** Model tests, role matrix tests, negative authorization tests.  
> **Dependencies:** IC-002. **Risk:** Changing AUTH_USER_MODEL after migrations is costly.

## Role and data-access matrix (source baseline)

| Actor | Shared IT docs | Private Web docs | My Credentials |
| --- | --- | --- | --- |
| App Admin | Only through separately assigned IT role | Own documents only | Own vault only |
| IT Doc Admin | Manage categories/docs; audited permanent deletion | Own documents only | Own vault only |
| IT Editor | Create, revise, publish, archive; review corrections | Own documents only | Own vault only |
| IT Member | View/search published and archived; request corrections | Own documents only | Own vault only |

Application administration and IT documentation administration are separate privileges. Backend queries and service operations must enforce authorization; UI hiding is not an authorization boundary.

## Proposed implementation boundaries for PO review

1. Introduce a custom Django user model with **unique email identity**, password hashing, and `is_active` behavior. Configure `AUTH_USER_MODEL` **before any auth-related migration**.
2. Model App Admin as an independent boolean privilege and IT role as a separate enumerated field (IT Doc Admin, IT Editor, IT Member, or no IT role). App Admin must not implicitly receive any IT documentation privilege.
3. Provide backend policy helpers for shared IT documentation actions and owner-private Web documents/vault access. Default deny for absent roles or ownership. Do not add document/vault domain models or expose their data in this task.
4. Ensure disabled accounts are rejected by authentication/policy paths. Full session login/logout, CSRF and immediate session revocation belong to IC-004; account lifecycle/invitation/deletion belong to IC-006/IC-007.
5. Preserve the IC-002 health endpoint and existing contenttypes-only migration history. Design and review the user model's `0001_initial` migration and its dependency graph **before applying migrations to persistent MySQL**.
6. Provide deterministic role matrix and negative authorization tests (including App Admin without IT role, cross-owner private data, disabled user, and absence of privilege escalation). Avoid relying on UI-only checks.
7. Update all four TTDM task records, architecture and setup documentation, and capture real Windows 10 native MySQL migration evidence without exposing `.env` credentials.

## Proposed acceptance checks

| ID | Check |
| --- | --- |
| IC-003-AC-01 | Email is the unique login identity; duplicate email is rejected by database constraints and application validation as appropriate. |
| IC-003-AC-02 | Custom user model is configured as `AUTH_USER_MODEL` before auth migrations; migration sequence is documented and repeatable on native MySQL. |
| IC-003-AC-03 | Inactive users cannot authenticate or pass protected backend authorization checks. |
| IC-003-AC-04 | App Admin privilege and IT documentation role remain independent; App Admin alone does not grant shared IT doc permissions. |
| IC-003-AC-05 | Private Web documents and vault policy permits owner-only access regardless of App Admin or IT role. |
| IC-003-AC-06 | IT Doc Admin, IT Editor and IT Member permissions follow the source matrix, with explicit negative tests. |
| IC-003-AC-07 | IC-002 health API, structured errors and existing contenttypes migrations remain intact. |
| IC-003-AC-08 | Model, role matrix, negative authorization, system and migration tests are recorded with actual results. |

## Open design decisions — PO/SOL review before coding

- **Email canonicalization:** define case-insensitive uniqueness policy and its MySQL collation implications; ensure no duplicates differing only by case.
- **Django flags and privilege boundaries:** decide exact relationship of `is_staff`, `is_superuser`, and the separate App Admin flag; do not equate Django superuser with application authorization or owner-private access.
- **No-IT-role representation:** choose nullable/blank role or explicit enum value, with default-deny semantics.
- **Permission-helper interface:** define actions and inputs now without prematurely implementing IC-009 domain entities.
- **Migration sequence:** inspect the current native MySQL `django_migrations` state; review the first custom-user migration and subsequent Django auth dependencies before applying. Escalate conflicts rather than rewriting already-applied migrations.

## Verification and TTDM gates

- Record a migration inventory/graph before applying any new migrations; confirm IC-002 `contenttypes` state and protect existing data.
- Run model and uniqueness tests, role matrix and negative authorization tests, Django system checks, clean-database migrations and second-run idempotence, and IC-002 regression tests.
- Verify native Windows 10 MySQL where available; record limitations rather than claiming unexecuted results.
- SOL must review the final specification and migration decisions. **No implementation branch, code, PR, or merge is authorized by this planning draft.**
- After separate Product Owner implementation authorization, create a task branch from current `feature/core-platform`, implement with Codex, and submit a task PR targeting the feature branch. Feature-to-`main` release remains separately gated.
