# IC-008 review

**Status:** Three SOL G2 conditional findings remediated; exact-head re-review pending
**Date:** 2026-10-28
**Implementation commit reviewed locally:** `3385812fdccbb377282c482772af51042db7b068`
**SOL G2 exact head reviewed:** `d9ab7b23c0ef8eb2eeeb790625d71da4750660a3`
**Draft PR:** #13 targeting `feature/identity-administration`
**Remediation head:** Recorded in PR #13 and the handoff after the remediation commit because a commit cannot contain its own SHA

## Review checklist

- Branch ancestry verified before work: `origin/feature/identity-administration` was an ancestor of `origin/task/IC-008-audit-authorization-harness`; both initially resolved to `5a5c56e819cb11ebc203c1fc57b7a0a229a74b32` with zero divergence.
- Work occurred only on `task/IC-008-audit-authorization-harness`; no merge was performed.
- Model fields and database checks match the controlled vocabulary and privacy contract.
- Service exposes no arbitrary metadata or raw request channel; validation and warning text do not echo supplied values.
- Critical-event failure propagates inside the caller transaction. Denied-event recording is single-attempt and non-escalating, and refuses to insert unless it is in autocommit outside atomic blocks.
- Existing authorization remains default deny and owner-only with no App Admin bypass.
- Existing auth routes, session behavior, CSRF enforcement, and API errors are unchanged and regression tested.
- Migration applied and tested on native MySQL; second migration and migration check passed.
- No forbidden lifecycle, invitation, permanent deletion, retention, viewing endpoint, deployment, or unrelated work was added.

## G2 finding resolution

1. **Living status:** all four documents now identify draft PR #13, the G2 conditional decision, exact reviewed head `d9ab7b23c0ef8eb2eeeb790625d71da4750660a3`, and pending remediation-head re-review.
2. **Denied transactions:** the service checks `in_atomic_block` and `get_autocommit()` before inserting. Tests prove autocommit persistence and prove atomic/manual-nonautocommit calls are skipped before insert.
3. **Vocabulary/identifiers:** the specification and implementation document the owning-task expansion/migration/review process. Tests cover numeric account IDs and canonical UUID/hex invitation-compatible IDs; a future invitation-specific target type remains an explicit IC-006 addition.

## Unresolved risks

- Audit rows can still be changed by direct database operators or bulk ORM operations with sufficient privileges; database access control is outside this task.
- Retention and IC-024 interaction are deliberately unresolved pending Product Owner policy.
- Event emission is not yet integrated into account lifecycle operations because IC-006 and IC-007 implementation is excluded.
- The existing vocabulary does not yet include all planned IC-006/IC-007 actions or an invitation-specific target type; those require new forward migrations and separately authorized task review.
- Local evidence does not substitute for CI or SOL exact-head review.
