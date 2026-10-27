# TTDM feature registry

Feature-based development is defined in [TTDM-WA-001](../process/TTDM-WA-001.md). The policy is proposed for operational adoption and requires a separately approved governance PR merge.

Maintain **one feature-level record** per approved feature at `docs/features/<feature-id>-<slug>.md`, based on [FEATURE-TEMPLATE.md](FEATURE-TEMPLATE.md). Every Task Code still maintains its four records under `docs/tasks/IC-NNN/`.

## Proposed feature groups (not implementation authorization)

| Feature | Name | Tasks | Status |
| --- | --- | --- | --- |
| F-00 | Foundation | IC-001 | Merged under original TTDM workflow; documentation closeout separate |
| F-01 | Core Platform | IC-002–IC-005 | Not started |
| F-02 | Identity & Administration | IC-006–IC-008, IC-024 | Not started; IC-024 dependency must be resolved |
| F-03 | Documentation Management | IC-009–IC-017 | Not started |
| F-04 | Copilot | IC-018–IC-020 | Not started |
| F-05 | Credentials Vault | IC-021–IC-023 | Not started |
| F-06 | MVP Acceptance | IC-025 | Not started |

Standalone low-risk tasks may follow the Product Owner-authorized [Section 3A fast track](../process/TTDM-WA-001.md#section-3a--standalone-task-fast-track-controlled-exception) without joining a feature. Such tasks still require a reviewed PR and Product Owner approval before merging into `main`.

Do not create feature branches or begin Task Codes solely because they appear in this registry.
