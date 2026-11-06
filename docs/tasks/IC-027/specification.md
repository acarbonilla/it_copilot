# IC-027 Specification — Bounded Artifact Inventory Remediation

**Status:** Implemented; SOL G2 review pending
**Baseline:** `2ef70e76eb8a3f992fc1fd2266269fcf3a662001`
**Feature status:** F-03 remains G2 HOLD; PR #22 is not authorized for merge.

Inventory separates a findings limit from an invocation work budget. `--limit` remains the maximum findings returned, `--work-limit` defaults to 5,000 and is capped at 10,000, and `--cursor` continues an incomplete signed page. Database phases use keyset batches of at most 256. Directory snapshots use `os.scandir`, inspect at most 4,097 entries, materialize/sort at most 4,096, and fail closed on overflow.

Work is charged for database candidates, directory opens/entries, bounded reference classification, and 64 KiB integrity chunks. Inventory is complete only after every phase terminates normally. Exhausted work/findings return an opaque continuation; invalid/expired/scope-mismatched cursors, filesystem/database failures, stale snapshots, and capacity errors never report completion.

Cursors expire after 24 hours and are signed, actor-bound, private-root-bound, settings-bound, and versioned. Stable inventory has deterministic continuation. Mutation of the current snapshotted directory invalidates its cursor; insertions behind the forward cursor are deferred to a later complete run.

The extracted namespace has an explicit 4,096-version-directory capacity ceiling. Capacity remediation or storage resharding is outside IC-027. Inventory remains observational; IC-026 execution-time quarantine/publication safeguards are unchanged.
