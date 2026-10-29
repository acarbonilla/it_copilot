# F02-SEC-001 — Review

**Gate:** G2 review requested  
**Merge:** Prohibited; PR targets `feature/identity-administration` only  
**Date:** 2026-10-29

## SOL review focus

1. Confirm the static route never serializes a token and the removed legacy route cannot render or reflect one.
2. Confirm migration ordering gives existing rows `LEGACY_PATH` and new rows `FRAGMENT_V1` without model drift.
3. Confirm command actor qualification, guard/user/invitation lock ordering, lock-time revalidation, per-record atomicity, idempotence, and expired-without-reissue behavior.
4. Confirm audit events contain actor IDs and invitation UUIDs only—never raw tokens, digests, email, URLs, or free text.
5. Confirm delivery collision/partial-write/commit/audit failures preserve pre-existing artifacts and roll back database state.
6. Confirm CSRF, password policy, single-use activation, lifecycle, authorization, fresh-login, and last-admin regressions remain green.

## Disposition requested

Review the exact task-branch head and attached evidence. Do not merge without Product Owner exact-head authorization. Do not run the execution mode against non-test data without a separate operational approval.
