# TTDM feature registry

Feature-based development is defined in [TTDM-WA-001](../process/TTDM-WA-001.md). The policy is proposed for operational adoption and requires a separately approved governance PR merge.

Maintain **one feature-level record** per approved feature at `docs/features/<feature-id>-<slug>.md`, based on [FEATURE-TEMPLATE.md](FEATURE-TEMPLATE.md). Under ratified TTDM clarification C4, each meaningful task checkpoint maintains one primary Markdown record by default plus feature-level updates where necessary; additional task records are optional when they materially improve traceability, not a mandatory four-file pattern.

## Proposed feature groups (not implementation authorization)

| Feature | Name | Tasks | Status |
| --- | --- | --- | --- |
| F-00 | Foundation | IC-001 | Merged under original TTDM workflow; documentation closeout separate |
| F-01 | Core Platform | IC-002–IC-005 | **Feature Completed**; PO accepted; [PR #9](https://github.com/acarbonilla/it_copilot/pull/9) merged into `main`; [acceptance review](F-01-acceptance-review.md) |
| F-02 | Identity & Administration | IC-006–IC-008 plus F02-SEC-001; IC-024 deferred | Merged to `main` through PR #21; historical closeout record predates that merge; IC-024 remains deferred |
| F-03 | Documentation Management | IC-009–IC-017 | Merged to `main` through PR #22; [post-merge verification](../02-Development/IC-030-F03-integration-post-merge-verification.md) complete with accepted limitations |
| F-04 | Copilot | IC-018–IC-020 | **Formally closed** following Product Owner-authorized PR #26 merge; historical [post-merge verification](../02-Development/F-04-post-merge-verification-and-closure.md) retains its pre-closure snapshot |
| F-05 | Personal Credential Vault | IC-021–IC-023 | **G1 RATIFIED — IC-021–IC-023 IMPLEMENTATION NOT YET AUTHORIZED**; [ratified contract](F-05-consolidated-g1-proposal.md) |
| F-06 | MVP Acceptance | IC-025 | Not started |

Standalone low-risk tasks may follow the Product Owner-authorized [Section 3A fast track](../process/TTDM-WA-001.md#section-3a--standalone-task-fast-track-controlled-exception) without joining a feature. Such tasks still require a reviewed PR and Product Owner approval before merging into `main`.

Do not create feature branches or begin Task Codes solely because they appear in this registry.

## Unassigned historical capability backlog

Earlier requirements referenced owner-private Web-document or “Documentation Workspaces” capabilities that are not the accepted F-03 Documentation Management scope: personal workspaces, collaboration/sharing, workspace membership, ownership transfer, correction requests, and editorial review workflows. They remain outstanding product-discovery items. This registry does not silently assign them to F-03, F-05, or new Task Codes, and records no implementation authorization for them.
