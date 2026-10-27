# TTDM task index

| Task | Title | Implementation state | Approval state |
| --- | --- | --- | --- |
| [IC-001](IC-001/specification.md) | Monorepo and Local Developer Setup | Merged into `main` via [PR #1](https://github.com/acarbonilla/it_copilot/pull/1), commit [`1cc1609a`](https://github.com/acarbonilla/it_copilot/commit/1cc1609a017dc25687b81163a04914292ed5b101) | SOL passed; Product Owner accepted; PR #2 closed without merge; documentation closeout [PR #4](https://github.com/acarbonilla/it_copilot/pull/4) merged |
| [IC-002](IC-002/specification.md) | Django/MySQL Core and Health API | Verified and integrated into `feature/core-platform` via [PR #5](https://github.com/acarbonilla/it_copilot/pull/5) | SOL passed |
| [IC-003](IC-003/specification.md) | Custom User Model and Roles | Verified and integrated into `feature/core-platform` via [PR #6](https://github.com/acarbonilla/it_copilot/pull/6) | SOL passed |
| [IC-004](IC-004/specification.md) | Session Authentication and CSRF | Verified and integrated into `feature/core-platform` via [PR #7](https://github.com/acarbonilla/it_copilot/pull/7) | SOL passed |
| [IC-005](IC-005/specification.md) | Next.js Shell and Login | Verified and integrated into `feature/core-platform` via [PR #8](https://github.com/acarbonilla/it_copilot/pull/8) | SOL passed |

## TTDM workflow amendment

[TTDM-WA-001](../process/TTDM-WA-001.md) was merged through [PR #3](https://github.com/acarbonilla/it_copilot/pull/3), commit [`ff4d8ac`](https://github.com/acarbonilla/it_copilot/commit/ff4d8ac15c2efda2f2cd47428beb5a300457c78d). The [feature registry](../features/README.md) provides proposed task-to-feature groupings, not authorization to start work.

A feature-scoped task is **Task Verified** following SOL-approved task integration into its feature branch. A feature is **Feature Completed** only after Product Owner-approved feature merge to `main` and documented closeout.

The **Standalone Task Fast Track** allows a small, independent, low-risk task to target `main` via a reviewed task PR. SOL assesses the exception; the Product Owner authorizes the classification and the exact task PR merge. Direct pushes to `main` are not permitted under normal TTDM workflow.

IC-001 was merged under the earlier workflow; do not rewrite its history. IC-002 and F-01 still require separate authorization.
