# IC-026 Specification — Orphan Artifact Quarantine Concurrency Safety

**Status:** Implemented; native MySQL concurrency suite passed 7 tests; IC-026 SOL G2 review pending
**Baseline:** `ba6b1bcd6a52c355bcb2b40c0d85d97ffc171306`
**Finding:** F-03 G2 HOLD — orphan inventory could become stale before quarantine.

PR #22 is not authorized for merge. F-03 remains at G2 HOLD. IC-026-R01 adds separate remediation evidence without changing the prior seven-test result.

Quarantine and every original/extracted artifact-reference publication must acquire the singleton artifact-publication database row first. While holding that lock, quarantine revalidates both artifact tables. A successful quarantine records a durable storage-key tombstone in the same transaction as its critical audit event. Publishers reject tombstoned keys. Lock, validation, storage, tombstone, or critical-audit failure must not be reported as success.

The lock order is artifact-publication guard, then account/document/version/job rows. Physical purge and unrelated F-03 findings remain out of scope.
