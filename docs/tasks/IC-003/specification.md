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

## SOL-finalized technical design decisions — pending Product Owner approval

These are implementation design choices derived from the baseline, **not new requirements quoted from the original TTDM document**.

### D-01 — Email-based identity and uniqueness

- Use a custom `User` extending `AbstractBaseUser` with `PermissionsMixin`, `USERNAME_FIELD = "email"`, and no username login field. Supply a custom manager implementing `create_user` and `create_superuser`.
- Require nonblank valid email; normalize whitespace and canonicalize the entire email to lowercase on user creation and updates. Preserve a documented single canonicalization function for manager/model paths; do not assume Django's `normalize_email` lowercases the local part.
- Enforce a database-level unique email constraint with an explicitly verified case-insensitive MySQL collation (and application validation), so `User@Example.com` and `user@example.com` cannot coexist even if writes bypass the manager. Verify collation and actual constraint behavior on native MySQL. Do not use an application-only uniqueness check.
- Passwords use Django's password hashers; never store or log plaintext passwords.

### D-02 — Separate Django framework flags and App Admin

- Store independent `is_app_admin` (default `False`), `is_staff` (default `False`), `is_superuser` (default `False`), and `is_active` (default `True`).
- `is_staff` gates potential future Django admin-site access only; `is_superuser` is a Django framework permission flag. Neither flag nor `is_app_admin` automatically grants IT documentation privileges or access to someone else's private Web documents/vault.
- Application authorization MUST use explicit policy helpers rather than generic `has_perm` or a blanket `is_superuser` bypass. Never treat Django framework superuser as an exception to owner-private restrictions.
- A `create_superuser` path may set Django `is_staff` and `is_superuser` as required by Django, but MUST NOT silently set `is_app_admin` or an IT role. Provisioning and last-active-App-Admin protections are separately scoped to IC-006/IC-007.
- Disabled users (`is_active=False`) fail every protected application policy; IC-004 must enforce inactive login rejection and immediate access invalidation.

### D-03 — Single IT role with explicit no-role default

- Define `TextChoices` values `NONE`, `IT_DOC_ADMIN`, `IT_EDITOR`, `IT_MEMBER`. Store `NONE` as a non-null default. App Admin is a separate boolean, not an IT role.
- An active user with `NONE` cannot access shared IT documents merely by holding `is_app_admin`, `is_staff`, or `is_superuser`.
- Roles do not confer access to another user's private Web documents or vault. The role matrix in this specification remains authoritative; avoid assuming a role hierarchy beyond the listed actions.

### D-04 — Backend policy-helper contract

- Expose small, testable policy functions (suggested interfaces: `can_manage_it_categories(user)`, `can_create_it_document(user)`, `can_revise_it_document(user)`, `can_publish_it_document(user)`, `can_archive_it_document(user)`, `can_view_it_document(user, *, published, archived)`, `can_request_correction(user)`, `can_delete_it_document_permanently(user)`, and `can_access_private_resource(user, *, owner_id)`).
- All helpers deny `None`, anonymous, inactive, and unrecognized-role users. The private-resource helper requires authenticated active user identity matching `owner_id`; there is no admin/superuser bypass.
- IT Doc Admin: manage shared IT categories/documents and authorize audited permanent deletion (audit implementation belongs to IC-008); IT Editor: create, revise, publish, archive and review corrections; IT Member: view/search published or archived shared documents and request corrections. For ambiguous actions, default deny and request PO clarification rather than expanding privileges.
- IC-003 delivers only role/policy logic and tests, not document/vault models, queries, UI, audit events, or CRUD endpoints. Later IC-009/IC-021 must enforce these policies in actual backend query and service paths.

### D-05 — Custom-user-first migration graph

1. Inspect and record the native MySQL `django_migrations` table, existing schema, and IC-002 contenttypes-only migration history. Confirm no auth/admin/session migration was previously applied; stop and escalate if present.
2. Implement the custom user model in a new app's `0001_initial` migration and set `AUTH_USER_MODEL` to that model before enabling Django auth/admin/session apps or applying their migrations.
3. Explicitly review the generated migration graph, including `swappable_dependency(settings.AUTH_USER_MODEL)`, Django auth/contenttypes dependencies, and any circular dependencies, before touching persistent MySQL. Do not edit previously applied IC-002 migrations.
4. Use a disposable fresh database for first migration verification; then migrate the approved persistent native MySQL database, repeat migrations to confirm `No migrations to apply`, and verify custom user tables and email uniqueness. Back up or otherwise protect existing local data before schema changes.
5. If the graph cannot be applied safely, STOP and escalate to SOL/PO. Do not silently fall back to Django's default `auth.User`.

### Mandatory negative tests

- Duplicate email differing only in case is rejected by the actual database constraint.
- App Admin with IT role `NONE` is denied shared IT document actions; framework superuser alone is likewise denied.
- All private Web-document/vault access to a different owner is denied for every IT role and every admin flag combination.
- Inactive and anonymous users are denied by all policy helpers.
- Role/action matrix, clean and repeated MySQL migrations, and IC-002 health regression pass. Record what was actually executed and any environment limitations.

**Approval gate:** SOL has finalized these five technical recommendations for PO decision. This revision is planning-only. No IC-003 implementation branch, coding, PR, or merge is authorized until separate explicit PO authorization.

## Verification and TTDM gates

- Record a migration inventory/graph before applying any new migrations; confirm IC-002 `contenttypes` state and protect existing data.
- Run model and uniqueness tests, role matrix and negative authorization tests, Django system checks, clean-database migrations and second-run idempotence, and IC-002 regression tests.
- Verify native Windows 10 MySQL where available; record limitations rather than claiming unexecuted results.
- SOL must review the final specification and migration decisions. **No implementation branch, code, PR, or merge is authorized by this planning draft.**
- After separate Product Owner implementation authorization, create a task branch from current `feature/core-platform`, implement with Codex, and submit a task PR targeting the feature branch. Feature-to-`main` release remains separately gated.
