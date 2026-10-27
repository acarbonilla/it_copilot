# F-01 — Core Platform

**Status:** In Development — IC-002 Verified and integrated
**Feature branch:** `feature/core-platform`  
**Approved base:** `main` at `cfeb19bf541aba962f9733289b905973d26361db`  
**Product Owner scope approval:** 2026-10-27  
**SOL review:** IC-002 PASS; remaining tasks pending

## Scope and dependencies

Build the Django/MySQL core, custom user roles, session authentication/CSRF, and Next.js shell/login. Feature is dependent on accepted IC-001 foundation.

| Task | Objective | Current state |
| --- | --- | --- |
| [IC-002](../tasks/IC-002/specification.md) | Django/MySQL Core and Health API | Verified; merged into feature branch via PR #5 |
| [IC-003](../tasks/IC-003/specification.md) | Custom User Model and Roles | Implementation in progress |
| IC-004 | Session Authentication and CSRF | Not started |
| IC-005 | Next.js Shell and Login | Not started |

## Task verification matrix

| Task | Task PR | SOL review | Task Verified | Integration commit |
| --- | --- | --- | --- | --- |
| IC-002 | [#5](https://github.com/acarbonilla/it_copilot/pull/5) | PASS at `35722ac047a6ba32d2eab4940108971db11650cc` | Yes | `1ad9dcaaa8c0002155311e9aabed68a0838df935` |
| IC-003 | Not created | Pending | No | — |
| IC-004 | Not created | Pending | No | — |
| IC-005 | Not created | Pending | No | — |

Each Task Code requires its four TTDM records and its own authorized implementation and SOL-reviewed integration gate.

## Integration and regression evidence

IC-002 was integrated after SOL review: 10 automated tests, native Windows MySQL connectivity, repeatable contenttypes-only migrations, health 200/503 contracts, JSON renderer, and finite MySQL timeouts are recorded in [IC-002 test results](../tasks/IC-002/test-results.md). A real stalled-read condition was not induced; mocked error behavior and configured read timeout were accepted for this local scope. No GitHub Actions checks were reported. Remaining F-01 task/regression evidence is pending.

## Recovery checkpoints

IC-002 task integration checkpoint: PR #5 reviewed head `35722ac047a6ba32d2eab4940108971db11650cc`, integration merge SHA `1ad9dcaaa8c0002155311e9aabed68a0838df935`. Maintain further checkpoints before IC-003/IC-004 authentication migration and feature release per [TTDM-WA-001](../process/TTDM-WA-001.md).

## SOL recommendation and Product Owner decision

- F-01 scope and IC-002 implementation were authorized on 2026-10-27.
- SOL expressly authorized IC-002 PR #5 task-to-feature merge for the reviewed exact head, and it was merged. No blanket authorization for other task merges or feature-to-main release is implied.
- Task-to-feature merges require SOL approval; feature-to-`main` release requires separate Product Owner approval against the exact head SHA.

## Merge and closeout

- Target: `main`
- Feature PR: Not created
- Feature merge SHA: Not applicable
- Feature Completed: **No**
