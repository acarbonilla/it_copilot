# F-01 — Core Platform feature-level acceptance review

**Date:** 2026-10-27  
**Method:** TTDM-WA-001  
**Scope:** IC-002, IC-003, IC-004, IC-005  
**Status:** SOL feature-level technical acceptance recommended; **Product Owner final acceptance and feature-to-main authorization pending**  
**Source:** IT Support Copilot V1.0 MVP TTDM Development Specification, IC-002–IC-005 task sections.

## Baseline acceptance scope

- IC-002: Django/DRF native MySQL foundation, repeatable migrations, safe health API and connection failures.
- IC-003: email-based custom user, distinct App Admin/IT role policy, inactive account rejection, ownership and role denials.
- IC-004: Django session login/logout/current-user, CSRF on unsafe calls, immediate access denial after deactivation, cookie replay denial.
- IC-005: Next.js App Router login, protected dashboard shell, identity restoration on refresh, logout, clearly labeled nonfunctional module placeholders.

F-01 is a **core-platform feature**, not acceptance of the entire IT Support Copilot V1.0 MVP. Invitations/activation, administrative lifecycle, documentation, Copilot and credentials vault functionality remain later features.

## Verified task integrations

| Task | PR | SOL-approved task head | Integration merge |
| --- | --- | --- | --- |
| IC-002 | #5 | `35722ac047a6ba32d2eab4940108971db11650cc` | `1ad9dcaaa8c0002155311e9aabed68a0838df935` |
| IC-003 | #6 | `e79bcec6067e04623401be7b2c724d54fac98e53` | `5dec944fea94c3f6433cd4c7fd1018d317504198` |
| IC-004 | #7 | `c37151292b5ec9a2ecb9e87a2765196dd09b08c9` | `20bdc4e83b24f5de3ddc9a8f4455dcc3c5bedf6c` |
| IC-005 | #8 | `7073d54fe0d0ce985e0b062f4cdbb306804479f8` | `98d6c28ce48632d4413d10ef80eb3b85cb9ec295` |

All four PRs are merged into `feature/core-platform` and task-level SOL reviews passed.

## Acceptance matrix and evidence

| Requirement | Recorded verification | SOL assessment |
| --- | --- | --- |
| Django/MySQL health, error handling, repeatable migration | IC-002 native MySQL, health 200/503, timeout and migration evidence | Pass |
| Email custom User, role and ownership boundaries | IC-003 unique email, inactive account, role matrix and cross-owner denials | Pass |
| Session auth, CSRF and deactivation | IC-004 login/logout/me, CSRF negatives, replay denial, migration | Pass |
| Browser login, refresh, logout, placeholders | IC-005 TypeScript/lint/build, 17/17 unit/API tests and 1/1 real two-tab Edge E2E | Pass |
| Integrated backend regressions | IC-005 reports 45/45 IC-002/003/004 tests passing | Pass |
| GitHub integration scope | GitHub compare: feature 36 commits ahead, 0 behind `main` at review time | Pass |

## Review limitations and residual controls

1. SOL inspected code diffs at the exact task PR heads and accepted committed test records. SOL did not independently execute the native Windows/MySQL/Edge workstation test suites.
2. No GitHub Actions workflow runs or commit statuses were available; local evidence was used.
3. The F-01 feature record contains historical checkpoint prose that says later tasks were pending. Those passages are dated historical records; the current task matrix supersedes them.
4. The feature registry `docs/features/README.md` retains a planning-era `F-01 Not started` entry. This is documentation drift and should be corrected during feature closeout; it does not change tested runtime behavior.
5. IC-006 onward, production deployment, hosted environments and full MVP functionality are explicitly outside F-01 acceptance.

## SOL feature-level disposition

**Technical acceptance recommended.** All in-scope task contracts have recorded passing verification and their SOL-reviewed PR heads are integrated. No known blocking F-01 runtime defect remains in the reviewed evidence.

**Product Owner gate:** Inspect this report and the feature-to-main PR against the exact feature branch head, then explicitly approve or request changes. **Do not merge to `main` before that approval.** Following approval and merge, record the actual feature merge SHA and mark F-01 Feature Completed. A feature-level PR may be prepared for PO review but preparation is not merge authorization.
