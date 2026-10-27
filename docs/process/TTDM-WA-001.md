# TTDM-WA-001 — Feature-Based Branching and Integration

**Project:** IT Support Copilot V1.0 MVP  
**Policy:** Product Owner approved 2026-10-26  
**Operational status:** Proposed; effective only after the governance PR is separately approved, merged, and recorded  
**Scope:** IC-002 onward; IC-001 retains its original approved history

## Purpose and authority

Individual Task Codes are implemented and reviewed separately. Related tasks integrate into a feature branch; only a complete, accepted feature is eligible to merge into `main`. A small, independent, low-risk standalone task may instead use the controlled direct-to-main PR exception below. Neither route permits direct pushes to `main`.

- **Product Owner:** authorizes feature scope and each Task Code specification; explicitly approves feature-to-`main` merges against an exact PR head.
- **SOL:** reviews task acceptance evidence and authorizes task-to-feature merges; verifies integration, security, regression, and recovery evidence; recommends feature acceptance.
- **Codex/Cursor:** implements only authorized tasks, supplies tests and documentation, prepares PRs and recovery checkpoints, and does not infer merge authorization.

## Branch naming and protection

| Purpose | Pattern | Base | PR target |
| --- | --- | --- | --- |
| Stable approved baseline | `main` | — | — |
| Feature integration | `feature/<feature-slug>` | approved `main` | `main` |
| Feature Task Code | `task/IC-NNN-<slug>` | relevant feature commit | corresponding feature |
| Standalone Task Code | `task/IC-NNN-<slug>` | approved `main` | `main` (exception only) |
| Recovery checkpoint | `backup/<feature-slug>/<checkpoint-id>` | exact verified feature SHA | never merge directly |
| Governance/docs | `docs/<slug>` | approved `main` | `main` |
| Narrow maintenance | `fix/<slug>` | approved `main` | `main` |

Use lowercase hyphenated slugs, stable Task Codes, unique checkpoint IDs, and explicit recorded commit SHAs. No normal direct pushes, force pushes, or deletion of `main`. Enable supported GitHub branch protection/rulesets only after checking repository capability; unavailable enforcement must be recorded as a limitation rather than claimed as active.

## Task lifecycle and gate

`New → Planned → In Progress → In Review → Task Verified`

A feature-scoped task is **Task Verified** only after its approved acceptance criteria, tests and exceptions, SOL review, and four living documents are complete, and its task PR has been authorized by SOL and merged into the correct feature branch. Task Verified does **not** mean deployed, merged into `main`, or feature-complete. A standalone task follows the separate completion gate below.

Required per-task records:
- `docs/tasks/IC-NNN/specification.md`
- `docs/tasks/IC-NNN/implementation.md`
- `docs/tasks/IC-NNN/test-results.md`
- `docs/tasks/IC-NNN/review.md`

Task PR merge permission is SOL-approved following review; Product Owner retains prior authorization of the Task Code scope.

## Section 3A — Standalone Task Fast Track (controlled exception)

A task may bypass the feature integration branch **only** when all of the following are documented:
1. The change is independently useful and does not depend on unmerged feature work.
2. Scope is small, bounded, low-risk, and independently testable.
3. It does not introduce material authentication, authorization, encryption, sensitive-data, schema-migration, architectural, or cross-feature integration risk.
4. SOL confirms no adverse effect on active feature branches and recommends the standalone classification.
5. The Product Owner **explicitly authorizes the standalone classification and task scope** before implementation.

**Flow:** `main` → `task/IC-NNN-<slug>` → reviewed task PR targeting `main` → Product Owner-approved merge → verified closeout.

- Codex implements only the approved scope and records acceptance criteria, tests, and all four task documents.
- SOL reviews the exact PR head, validates the evidence, and recommends acceptance.
- **The Product Owner explicitly approves the exact standalone PR head SHA before merging into `main`.** SOL's normal authority to merge tasks into feature branches does not extend to merging standalone tasks into `main`.
- If the PR head changes, approval must be renewed; no direct push or bypass of PR review is allowed.
- After successful merge, record the merge SHA and documentation closeout; the task is **Completed (Standalone)**, not Feature Completed.
- If a change proves interdependent or risky, stop and reclassify it into a feature through Product Owner approval.

Examples that *may* qualify after assessment: a README correction, isolated validation-script improvement, or small independent UI fix. A small diff alone does not establish low risk. Existing IC-001 history remains unchanged.

## Feature lifecycle and gate

`Planned → In Development → Integration Review → Awaiting Product Owner Approval → Feature Completed`

One feature record is maintained at `docs/features/<feature-id>-<slug>.md`, based on [FEATURE-TEMPLATE](../features/FEATURE-TEMPLATE.md).

Feature completion requires:
1. All included tasks Task Verified and dependency constraints resolved.
2. Integrated behavior, regression, security/permission and data-integrity tests appropriate to the feature recorded and accepted.
3. A known-good recovery checkpoint created and verified before feature release.
4. SOL recommendation and Product Owner authorization of the exact feature PR head SHA.
5. Successful feature PR merge into `main`, verified merge SHA, and completed living-documentation closeout.

If the PR head changes after authorization, the merge must be re-reviewed and reapproved. No unapproved unrelated Task Codes may enter the feature PR.

## Task-to-feature map (proposed integration grouping)

| Feature | Branch | Task Codes |
| --- | --- | --- |
| F-00 Foundation (historical) | `main` | IC-001 (already merged) |
| F-01 Core Platform | `feature/core-platform` | IC-002–IC-005 |
| F-02 Identity & Administration | `feature/identity-administration` | IC-006–IC-008 (PO-approved G0 planning scope, 2026-10-27); IC-024 deferred |
| F-03 Documentation Management | `feature/documentation-management` | IC-009–IC-017 |
| F-04 Copilot | `feature/copilot` | IC-018–IC-020 |
| F-05 Credentials Vault | `feature/credentials-vault` | IC-021–IC-023 |
| F-06 MVP Acceptance | `feature/mvp-acceptance` | IC-025 |

**Dependency constraint and approved planning amendment (2026-10-27):** Product Owner approved F-02 planning scope IC-006, IC-007, IC-008 and deferred IC-024 until IC-023 is available. IC-024 requires IC-007 and IC-023; its later feature placement and implementation require separate approval. This amendment is a documentation proposal until its governance PR is reviewed and approved for merge. **G0 planning approval does not authorize implementation, task branches, code, or merges.**

## Review gates

| Gate | Evidence | Authority |
| --- | --- | --- |
| G0 Feature scope | Included tasks, dependency plan | Product Owner |
| G1 Task specification | Acceptance criteria, bounded scope | Product Owner |
| G2 Task review | Code, tests, four living docs | SOL |
| G3 Task PR → feature | Exact reviewed task PR head and target | SOL |
| G3S Standalone classification | Independence, risk assessment, bounded scope | SOL recommends; Product Owner authorizes |
| G5S Standalone PR → main | Exact head SHA, task tests/docs, SOL recommendation | Product Owner |
| G4 Feature integration | Regression/security checks, recovery checkpoint, feature record | SOL |
| G5 Feature PR → main | Exact head SHA, SOL recommendation | Product Owner |
| G6 Closeout | Merge SHA and living-documentation evidence | SOL verifies; Product Owner accepts |

## Recovery checkpoint procedure

Before risky integration **and** before feature release:

1. Stop and confirm the feature branch's last known-good state, including relevant test results.
2. Record the full commit SHA, reason, time, and related task/PR in the feature record.
3. Create `backup/<feature-slug>/<unique-checkpoint-id>` pointing to that exact commit, push it, and verify the remote SHA matches.
4. Perform the integration only after the checkpoint is verified.
5. On failure, preserve logs, stop integration, and propose a reviewable fix or revert on the feature branch. Restore from the checkpoint using a new recovery branch if needed; never routinely reset/force-push `main`.
6. Retain the checkpoint until the feature merge and closeout are confirmed; remove only through approved cleanup.

A backup branch is a Git reference, not an independent offsite backup. Preserve remote history and enforce least privilege.

## Transition and exclusions

IC-001 was accepted and merged under the original task-based workflow; do not rewrite its history. PR #2 is an independent IC-001 documentation closeout and must not be merged under this amendment's authorization. The governance PR itself requires separate Product Owner merge approval.

No feature branches, IC-002 implementation, runtime, deployment, or cloud work is authorized by this amendment. The policy becomes operational only after the governance PR is approved, merged, and recorded.
