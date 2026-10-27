# IC-008 — Audit and Authorization Test Harness

**Status:** G1 design recommendations approved by Product Owner; specification documentation finalized for review; implementation prohibited  
**Feature:** F-02 Identity & Administration  
**Priority:** P0  
**Requested by:** Product Owner  
**Planned by:** SOL  
**Implemented by:** Not assigned  
**Reviewed by:** Pending  
**PR / commit:** Documentation planning PR only; no implementation PR  
**Dependencies:** IC-003 (complete in F-01)  
**Last updated:** 2026-10-27

## 1. Authoritative source contract

The original *IT Support Copilot V1.0 TTDM Development Specification*, section **IC-008 | Audit and authorization test harness**, states:
- **Objective:** Create reliable proof of sensitive-operation enforcement.
- **Implementation scope:** Structured audit event model and service, sanitization policy, reusable test factories and negative authorization scenarios.
- **Acceptance:** Sensitive actions record actor/action/target without secrets; cross-owner requests are rejected; tests are repeatable.
- **Verification:** Inspect log output; automated role/ownership matrix; audit event assertions.
- **Dependency:** IC-003. **Risk:** Accidental secret logging.

The original source does **not** specify an audit schema, event vocabulary, retention period, API endpoint, or delivery mechanism. The decisions below are **SOL proposed design details** for G1 review, not source-mandated requirements.

## 2. Scope boundary

**In scope (proposed):**
1. Django structured `SecurityAuditEvent` model and migration on native MySQL.
2. Central audit recording service with stable action identifiers and sanitization/allowlist policy.
3. Test factories for custom users, App Admin flags, IT roles, active/inactive state and ownership.
4. Repeatable positive/negative authorization matrices covering existing IC-003 policies and representative IC-004 protected API behaviors.
5. Integration contract for IC-006 invitation and IC-007 lifecycle operations to emit events when implemented.
6. Testable failure behavior, safe logging and TTDM living-document updates.

**Out of scope:** Implementing IC-006/007 workflows; sending invitations; user administration UI; vault/document models; permanent deletion; audit viewing/export UI; remote telemetry, cloud infrastructure or deployment. No new public audit endpoint is required.

## 3. G1-approved architecture direction and schema proposal

- Django app/module owns audit model and service; business operations call the service rather than writing raw logger messages.
- Proposed event fields: `id`, `action` (controlled vocabulary), `actor_user_id` (nullable), `target_type` (allowlisted), `target_id` (nullable opaque identifier), `outcome` (success/denied/failure), `occurred_at`, `request_id` (optional nonsecret correlation). Use an immutable, nonsecret actor user ID snapshot rather than a nullable FK; preserve historical attribution without coupling event survival to user deletion. IC-024 must separately define retention and deletion behavior.
- **Never store** passwords, activation token values or hashes, CSRF tokens, session identifiers, cookies, authorization headers, vault secrets, document contents or raw request bodies in audit payloads.
- Avoid unconstrained metadata dictionaries and free-text exception messages; prefer an allowlisted action-specific schema. Do not expose audit rows to ordinary users.
- Default-deny server-side permissions remain in `accounts/policies.py`; tests verify them without treating client-side role visibility as authorization.
- For future IC-006/007 operations, use transaction-aware event recording so successful state changes and their audit records are consistent; specify how denied attempts are audited outside rolled-back transactions.
- Retention period is not yet specified by the original source or PO. **Do not implement automated purge, deletion, or destructive cascade**. Record retention as a blocked operational decision for the later lifecycle/IC-024 policy; audit storage and bounded local test data may be designed without a purge job.

## 4. G1-approved acceptance criteria

| ID | Criterion | Minimum evidence |
| --- | --- | --- |
| IC-008-AC-01 | A structured audit record persists action, actor, target, outcome and timestamp for representative sensitive operations | Native MySQL model/migration and service tests |
| IC-008-AC-02 | Audit service rejects or strips all secret-bearing fields; no secrets appear in stored events or application logs | Sentinel-secret tests and captured log assertions |
| IC-008-AC-03 | Existing role/ownership policies default deny for anonymous, inactive, unknown-role and cross-owner subjects | Parameterized role/ownership matrix |
| IC-008-AC-04 | App Admin status alone does not grant IT document or private-resource ownership permissions | Negative matrix |
| IC-008-AC-05 | Existing authenticated endpoints maintain expected 401/403 and CSRF behavior without leaking details | API regressions |
| IC-008-AC-06 | Test factories isolate data and produce deterministic repeatable runs | Repeat suite and migration checks |
| IC-008-AC-07 | Audit recording failure behavior is explicitly specified and tested before integration with account mutations | Atomicity/failure-injection tests |
| IC-008-AC-08 | No plaintext secrets, new unauthorized routes, or F-02 account-lifecycle functionality are introduced | Code review, route diff, repository validation |
| IC-008-AC-09 | Four TTDM task documents, affected architecture/data-model references and native MySQL test evidence are complete | SOL exact-head review |

## 5. Proposed verification commands and evidence

Use the existing Django test-settings suite with explicit app labels, plus new audit app tests. Run native MySQL system check, migration plan, first/second migration, `migrate --check`, model-drift check, existing IC-002/003/004 regressions, repository validation and whitespace check. Record exact commands, environment, counts and limitations; no CI success may be claimed when unavailable.

## 6. Product Owner-approved G1 design decisions and remaining constraints

1. **Actor preservation (approved):** persist an immutable nonsecret actor ID snapshot. Do not depend on an FK that erases attribution upon user deletion.
2. **Audit failure semantics (approved):** for security-critical account mutations, audit persistence and the mutation must succeed or fail atomically; if audit persistence fails, fail closed and roll back the mutation. For denied attempts, attempt bounded best-effort audit outside rolled-back mutations, without leaking secrets or escalating denial to authorization.
3. **Event vocabulary (approved):** use controlled, versionable event names. Initial integration targets include `auth.login_success`, `auth.login_denied`, `account.invite_created`, `account.deactivated`, `account.reactivated`, `authorization.denied`; adding emission to existing IC-004 authentication handlers is not automatically authorized by IC-008 G1.
4. **Retention (approved constraint):** retention must be explicitly defined before any automatic cleanup; **no numerical retention period was approved**. Do not implement retention deletion jobs under IC-008. Later retention and IC-024 cleanup policy require a separate PO decision.
5. **Privacy (approved):** exclude email, IP addresses, passwords, tokens, cookies, session IDs, raw request payloads and other secrets by default. Use immutable nonsecret IDs and optional safe request correlation only.

## 7. TTDM gate

**G0:** F-02 planning scope IC-006/007/008 approved by PO; IC-024 deferred pending IC-023; F02-D01 through D08 approved as design baseline.  
**G1:** Product Owner approved IC-008 design recommendations on 2026-10-27 and authorized finalization of specification documentation only. This document records that design decision; its documentation PR remains draft/unmerged pending separate review.  
**Implementation:** **Not authorized.** G1 design approval and documentation finalization do not authorize any task branch, code, migration, runtime test execution or implementation PR. Separate explicit PO implementation authorization is required.  
**Documentation PR:** PR #10 is draft and unmerged. Review/merge requires its own separate approval; it is not an implementation authorization.
