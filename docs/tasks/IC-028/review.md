# IC-028 Review Record

**Codex status:** Implementation and required local evidence complete
**SOL status:** G2 review pending
**PO acceptance:** Pending
**Merge status:** Not authorized

| AC | Status | Evidence |
| --- | --- | --- |
| 01 | PASS | Guarded publication requires original reference and validates both artifacts. |
| 02 | PASS | Streaming storage and publication failure tests cover existence, size, and digest. |
| 03 | PASS | Both key tombstones reject publication without state mutation. |
| 04 | PASS | Publication mutations follow validation; invalid cases leave current unchanged. |
| 05 | PASS | Injected success-audit failure rolls back reference, READY/current/candidate/job changes. |
| 06 | PASS | Guarded compensation preserves referenced artifacts. |
| 07 | PASS | Two deterministic publication/invalid-reconciliation winner-order tests and the 10-test native MySQL concurrency suite passed without skips. |
| 08 | PASS | Invalid-current recovery clears the pointer; audit failure restores all prior state. |
| 09 | PASS | Lease, retry, retry-exhaustion, and duplicate-publication regressions pass. |
| 10 | PASS | Relevant regressions, migration consistency, Django check, and six documents pass. |
| 11 | PASS | Audit exceptions propagate; no success result is returned. |
| 12 | PASS | Database/reference-check failure preserves the file and raises unresolved cleanup. |
| 13 | PASS | 257-row read-only assessment proves continuation beyond a 256-row batch. |

## Known limitations

- The guarantee applies to controlled application services, not direct SQL or permanent filesystem availability.
- Physical assessment is opt-in and checks READY artifacts; database relationship/current-state checks are always enabled.
- If guarded cleanup cannot establish reference state, it intentionally leaves a possible orphan for IC-027 reconciliation.
- No automatic prior-version selection occurs when an invalid current pointer is cleared.

This record does not declare G2 PASS. F-03 remains G2 HOLD pending SOL review.

## G2-T01 evidence closure

The prior AC-07 evidence gap is closed by `test_publication_wins_against_invalid_artifact_reconciliation` at `documents/tests/test_reconciliation.py:334` and `test_invalid_artifact_reconciliation_wins_against_publication` at line 418. Both use independent MySQL connections, explicit row-lock contention, `threading.Event` acquisition/release signals, finite timeouts, and complete final-state/audit assertions. Publication-first proves stale-issue revalidation without forced invalidation. Reconciliation-first proves lease fencing and the absence of READY/current/SUCCEEDED/success-audit publication after committed invalidation. SOL G2 acceptance remains pending.
