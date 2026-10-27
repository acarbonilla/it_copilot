# F-01 — Core Platform

**Status:** Feature Completed — Product Owner accepted; merged into `main` via PR #9 on 2026-10-27
**Feature branch:** `feature/core-platform`  
**Approved base:** `main` at `cfeb19bf541aba962f9733289b905973d26361db`  
**Product Owner scope approval:** 2026-10-27  
**SOL review:** IC-002, IC-003, IC-004 and IC-005 PASS

## Scope and dependencies

Build the Django/MySQL core, custom user roles, session authentication/CSRF, and Next.js shell/login. Feature is dependent on accepted IC-001 foundation.

| Task | Objective | Current state |
| --- | --- | --- |
| [IC-002](../tasks/IC-002/specification.md) | Django/MySQL Core and Health API | Verified; merged into feature branch via PR #5 |
| [IC-003](../tasks/IC-003/specification.md) | Custom User Model and Roles | Verified; merged into feature branch via PR #6 |
| [IC-004](../tasks/IC-004/specification.md) | Session Authentication and CSRF | Verified; merged into feature branch via PR #7 |
| [IC-005](../tasks/IC-005/specification.md) | Next.js Shell and Login | Verified; merged into feature branch via PR #8 |

## Task verification matrix

| Task | Task PR | SOL review | Task Verified | Integration commit |
| --- | --- | --- | --- | --- |
| IC-002 | [#5](https://github.com/acarbonilla/it_copilot/pull/5) | PASS at `35722ac047a6ba32d2eab4940108971db11650cc` | Yes | `1ad9dcaaa8c0002155311e9aabed68a0838df935` |
| IC-003 | [#6](https://github.com/acarbonilla/it_copilot/pull/6) | PASS at `e79bcec6067e04623401be7b2c724d54fac98e53` | Yes | `5dec944fea94c3f6433cd4c7fd1018d317504198` |
| IC-004 | [#7](https://github.com/acarbonilla/it_copilot/pull/7) | PASS at `c37151292b5ec9a2ecb9e87a2765196dd09b08c9` | Yes | `20bdc4e83b24f5de3ddc9a8f4455dcc3c5bedf6c` |
| IC-005 | [#8](https://github.com/acarbonilla/it_copilot/pull/8) | PASS at `7073d54fe0d0ce985e0b062f4cdbb306804479f8` | Yes | `98d6c28ce48632d4413d10ef80eb3b85cb9ec295` |

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
- Feature PR: [#9](https://github.com/acarbonilla/it_copilot/pull/9)
- Feature merge SHA: `54c872d0bfc2f6bfe63cb5273afff5d14d0e9a9b`
- Feature Completed: **Yes**

## IC-003 integration checkpoint (2026-10-27)

PR #6 custom User/role-policy integration was SOL-reviewed at exact head `e79bcec6067e04623401be7b2c724d54fac98e53` and merged into the feature branch as `5dec944fea94c3f6433cd4c7fd1018d317504198`. Verification evidence: 29/29 combined IC-003/IC-002 tests, native MySQL migration/idempotence, role matrix/ownership negatives, blank-email regression, and live health check, as recorded in [IC-003 test results](../tasks/IC-003/test-results.md). No GitHub Actions CI check was available. F-01 remains in development; IC-004 and IC-005 are outstanding. No feature-to-`main` authorization is implied.

## IC-004 integration checkpoint (2026-10-27)

PR #7 session authentication/CSRF was SOL-reviewed at exact head `c37151292b5ec9a2ecb9e87a2765196dd09b08c9` and merged into the feature branch as `20bdc4e83b24f5de3ddc9a8f4455dcc3c5bedf6c`. Verification evidence in [IC-004 test results](../tasks/IC-004/test-results.md) records 45/45 combined tests, native MySQL session migration, CSRF/Origin negatives, deactivation/logout cookie replay denial, and cookie-aware local HTTP verification. No GitHub Actions CI was available; SOL did not independently execute workstation tests. F-01 remains in development with IC-005 outstanding; no feature-to-`main` authorization is implied.

## IC-005 integration checkpoint (2026-10-27)

PR #8 Next.js shell/login integration was SOL-reviewed at exact head `7073d54fe0d0ce985e0b062f4cdbb306804479f8` and merged into feature branch as `98d6c28ce48632d4413d10ef80eb3b85cb9ec295`. Verification evidence in [IC-005 test results](../tasks/IC-005/test-results.md) records 17/17 frontend API/component tests, 1/1 real two-tab Edge browser E2E, 45/45 backend regressions, typecheck/lint/build, and native MySQL checks. SOL reviewed code and recorded evidence, did not independently execute local tests; GitHub Actions CI unavailable.

**All IC-002 through IC-005 task integrations are complete.** F-01 requires separate feature-level review and explicit Product Owner approval of exact feature head before merge to `main`.

## F-01 final acceptance and closeout (2026-10-27)

Product Owner accepted F-01 technical verification and authorized the exact feature head `6350bec85b67f0b9caf672914f9a3eb76e9587e9` for merge into `main`, subject to final PR review. SOL inspected PR #9 at that head and recorded PASS. PR #9 was merged into `main` with merge commit `54c872d0bfc2f6bfe63cb5273afff5d14d0e9a9b`.

**F-01 Feature Completed: Yes.** This status applies only to Core Platform IC-002–IC-005, not to full MVP delivery or later feature groups. The final closeout documentation commit is post-merge administrative documentation and is not a change to the PO-reviewed feature head.
