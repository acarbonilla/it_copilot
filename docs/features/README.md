# TTDM feature registry

Feature-based development is defined in [TTDM-WA-001](../process/TTDM-WA-001.md). The policy is proposed for operational adoption and requires a separately approved governance PR merge.

Maintain **one feature-level record** per approved feature at `docs/features/<feature-id>-<slug>.md`, based on [FEATURE-TEMPLATE.md](FEATURE-TEMPLATE.md). Under ratified TTDM clarification C4, each meaningful task checkpoint maintains one primary Markdown record by default plus feature-level updates where necessary; additional task records are optional when they materially improve traceability, not a mandatory four-file pattern.

## Proposed feature groups (not implementation authorization)

| Feature | Name | Tasks | Status |
| --- | --- | --- | --- |
| F-00 | Foundation | IC-001 | Merged under original TTDM workflow; documentation closeout separate |
| F-01 | Core Platform | IC-002–IC-005 | **Feature Completed**; PO accepted; [PR #9](https://github.com/acarbonilla/it_copilot/pull/9) merged into `main`; [acceptance review](F-01-acceptance-review.md) |
| F-02 | Identity & Administration | IC-006–IC-008 plus F02-SEC-001; IC-024 deferred | Merged to `main` through PR #21 and integrated in the [accepted local MVP baseline](F-06-final-acceptance-review.md); historical [feature evidence](F-02-final-acceptance-review.md) preserved; IC-024 remains deferred |
| F-03 | Documentation Management | IC-009–IC-017 | **PASS WITH ACCEPTED LIMITATIONS**; merged through PR #22 and integrated in the accepted local MVP baseline; [post-merge verification](../02-Development/IC-030-F03-integration-post-merge-verification.md) |
| F-04 | Copilot | IC-018–IC-020 | **Formally closed** through PO-authorized PR #26 and integrated in the accepted local MVP baseline with provider/private-data transfer disabled; historical [post-merge verification](../02-Development/F-04-post-merge-verification-and-closure.md) preserved |
| F-05 | Personal Credential Vault | IC-021–IC-023 | **PASS WITH ACCEPTED LIMITATIONS**; PO accepted and integrated through PR #34; [final MVP reconciliation](F-06-final-acceptance-review.md) |
| F-06 | MVP Acceptance | IC-025 | **PASS WITH ACCEPTED LIMITATIONS — LOCAL MVP DEVELOPMENT ONLY**; PO accepted 2026-11-23 at `af768f16…`; [final acceptance review](F-06-final-acceptance-review.md) |

Standalone low-risk tasks may follow the Product Owner-authorized [Section 3A fast track](../process/TTDM-WA-001.md#section-3a--standalone-task-fast-track-controlled-exception) without joining a feature. Such tasks still require a reviewed PR and Product Owner approval before merging into `main`.

Do not create feature branches or begin Task Codes solely because they appear in this registry.

## Unassigned historical capability backlog

Earlier requirements referenced owner-private Web-document or “Documentation Workspaces” capabilities that are not the accepted F-03 Documentation Management scope: personal workspaces, collaboration/sharing, workspace membership, ownership transfer, correction requests, and editorial review workflows. They remain outstanding product-discovery items. This registry does not silently assign them to F-03, F-05, or new Task Codes, and records no implementation authorization for them.
