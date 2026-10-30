# IC-016 Implementation Record

- `documents.reconciliation` provides bounded inventory, actor validation, per-issue revalidation, stale-job recovery, invalid-artifact failure, and compensated orphan quarantine.
- `reconcile_documents` requires an actor and limit, prints controlled issue kinds/IDs, defaults to no mutation, and requires `--execute`.
- `PrivateArtifactStore.inventory_keys()` enumerates only allowlisted opaque original/extracted keys and fails closed on reparse points. `restore_quarantined()` compensates audit failure without accepting user paths.
- `document.reconciled` is added through forward audit migration `0008`.
- Private-root initialization verifies an already-correct strict ACL before attempting enforcement, enabling independent API/worker/recovery processes while remaining fail-closed.
- Upload-owned stores close their Windows replacement lock in `finally`; caller-provided stores remain caller-owned.

## Recovery checkpoint

Before any non-test execution, stop writers/workers and take a consistent native-MySQL backup plus a snapshot of the entire configured private root (originals, extracted, staging/quarantine). Record database snapshot time/identity and artifact snapshot identity together. Restore both sides together; if either side differs, run dry-run inventory before enabling API/worker traffic. No non-test recovery or purge was executed during development.
