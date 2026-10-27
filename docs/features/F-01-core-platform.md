# F-01 — Core Platform

**Status:** Planned — scope approved; IC-002 implementation awaiting separate approval  
**Feature branch:** `feature/core-platform`  
**Approved base:** `main` at `cfeb19bf541aba962f9733289b905973d26361db`  
**Product Owner scope approval:** 2026-10-27  
**SOL review:** Pending task implementation and integration

## Scope and dependencies

Build the Django/MySQL core, custom user roles, session authentication/CSRF, and Next.js shell/login. Feature is dependent on accepted IC-001 foundation.

| Task | Objective | Current state |
| --- | --- | --- |
| [IC-002](../tasks/IC-002/specification.md) | Django/MySQL Core and Health API | Specification drafted; implementation not authorized |
| IC-003 | Custom User Model and Roles | Not started |
| IC-004 | Session Authentication and CSRF | Not started |
| IC-005 | Next.js Shell and Login | Not started |

## Task verification matrix

| Task | Task PR | SOL review | Task Verified | Integration commit |
| --- | --- | --- | --- | --- |
| IC-002 | Not created | Pending | No | — |
| IC-003 | Not created | Pending | No | — |
| IC-004 | Not created | Pending | No | — |
| IC-005 | Not created | Pending | No | — |

Each Task Code requires its four TTDM records and its own authorized implementation and SOL-reviewed integration gate.

## Integration and regression evidence

Not available: no task implementation or integration has begun. Relevant security, authentication, database, and regression checks will be specified and verified as tasks progress.

## Recovery checkpoints

Not yet required: none of the risky integrations or feature release gates has occurred. Create and verify a checkpoint before each such event per [TTDM-WA-001](../process/TTDM-WA-001.md).

## SOL recommendation and Product Owner decision

- F-01 scope authorized, but no implementation or merge authorization is implied.
- IC-002 specification requires separate Product Owner approval.
- Task-to-feature merges require SOL approval; feature-to-`main` release requires separate Product Owner approval against the exact head SHA.

## Merge and closeout

- Target: `main`
- Feature PR: Not created
- Feature merge SHA: Not applicable
- Feature Completed: **No**
