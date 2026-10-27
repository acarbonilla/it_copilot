# TTDM task index

| Task | Title | Implementation state | Approval state |
| --- | --- | --- | --- |
| [IC-001](IC-001/specification.md) | Monorepo and Local Developer Setup | Merged into `main` via [PR #1](https://github.com/acarbonilla/it_copilot/pull/1) | Product Owner accepted; documentation closeout [PR #2](https://github.com/acarbonilla/it_copilot/pull/2) remains separate |
| IC-002 | Django/MySQL Core and Health API | Not started | Requires separate approval |

## Proposed TTDM workflow amendment

[TTDM-WA-001](../process/TTDM-WA-001.md) introduces **Task Verified** for SOL-reviewed task merges into feature branches and **Feature Completed** for Product Owner-approved feature merges into `main`. The [feature registry](../features/README.md) is a proposed grouping, not permission to start work.

The amendment also proposes a **Standalone Task Fast Track**: SOL assesses low-risk independence, the Product Owner authorizes classification and the exact task PR merge into `main`, and the task receives a verified standalone closeout. No direct pushes to `main`.

The amendment becomes effective only after its governance PR is approved and merged. This change must not be used to merge PR #2 or authorize IC-002.
