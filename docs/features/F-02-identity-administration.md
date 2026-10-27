# F-02 — Identity & Administration

**Status:** Planned — G0 approved; IC-008 G1 design approved, documentation PR review pending  
**Proposed branch:** `feature/identity-administration` (not created)  
**Product Owner G0 authorization:** 2026-10-27 — planning only  
**SOL reviewer:** SOL  
**Implementation authorization:** None

## Scope and dependencies

- **Included tasks:** IC-008 Audit and authorization test harness; IC-006 invitation and activation; IC-007 App Admin account lifecycle.
- **Proposed sequence:** IC-008 → IC-006 → IC-007. IC-008 depends on IC-003 (complete); IC-006 depends on IC-003 and IC-004 (complete); IC-007 depends on IC-006.
- **Deferred:** IC-024 Account deletion safeguards and cleanup, pending IC-023 vault dependency and IC-007; requires separate feature/task placement approval before implementation.
- **Excluded:** Permanent account deletion, vault data cleanup, self-registration, deployment, hosted services and later feature functions.
- **F-01 baseline:** F-01 completed in `main` via PR #9; custom User, roles, sessions and CSRF are existing security boundaries.

## Approved architecture baseline

| Decision | G0-approved direction |
| --- | --- |
| F02-D01 | Hashed, single-use, expiring activation tokens |
| F02-D02 | Django password validators; define minimum policy in IC-006 G1 |
| F02-D03 | Development-safe email output without secret logging |
| F02-D04 | App Admin authorization separate from IT role |
| F02-D05 | Revoke sessions on deactivation and deny immediately |
| F02-D06 | Transactional last-active-App-Admin safeguards |
| F02-D07 | Audit infrastructure before sensitive lifecycle integration |
| F02-D08 | Deletion review only; defer permanent deletion/cleanup to IC-024 |

## Task verification matrix

| Task | G1 specification | Implementation | SOL review | Task Verified |
| --- | --- | --- | --- | --- |
| IC-008 | [G1 design approved; specification finalized for documentation review](../tasks/IC-008/specification.md) | Not authorized | Pending | No |
| IC-006 | Not drafted | Not authorized | Pending | No |
| IC-007 | Not drafted | Not authorized | Pending | No |
| IC-024 | Deferred pending IC-023 | Not authorized | Not applicable | No |

Each implemented task must maintain four TTDM living documents and pass its individual G1/G2/G3 gates.

## Integration and regression evidence

Not applicable — no F-02 implementation has begun. Proposed checks: role/ownership negative matrices, invitation token replay/expiry, deactivation/session invalidation, last-admin concurrency, audit secret redaction, native MySQL migration/regressions, and real-browser administration flow.

## Recovery checkpoints

Not created. Before risky implementation integration and feature release, record and verify exact remote backup ref per TTDM-WA-001.

## SOL recommendation

G0 scope approved for planning. Prepare IC-008 G1 specification, then IC-006 and IC-007. No code or feature-to-main authorization.

## Product Owner decision

2026-10-27: approved F-02 scope IC-006/007/008, deferred IC-024 until IC-023, approved F02-D01 through D08 **as design baseline only**. Explicitly withheld implementation, task coding and merge authorization.

## Merge and closeout

- Target: `main` eventually; no feature PR.
- Feature merge SHA: None.
- Feature Completed: **No**.

## IC-008 G1 decision (2026-10-27)

Product Owner approved IC-008 G1 recommendations for immutable nonsecret actor IDs, fail-closed atomic audit on critical mutations, bounded best-effort denied-event logging, controlled versionable event vocabulary, retention-before-cleanup, and default exclusion of email/IP/secrets/raw payloads. Authorized **specification documentation finalization only**. No implementation, task coding, or merge authorized. Draft documentation PR #10 remains subject to separate review and merge authorization.
