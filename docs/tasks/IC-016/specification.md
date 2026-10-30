# IC-016 Specification - Reconciliation, Recovery, and Operator Controls

**Baseline:** `6cd50f2a0ce041a2955e8e582bba44ce06ad6950`

- `reconcile_documents --actor-id <id>` is bounded and dry-run by default; `--execute` is required for mutation.
- The actor must be an active, activated App Admin. Recovery authority grants no document-content API access.
- Inventory reports expired leases, missing/digest-or-size-invalid artifacts, database-unreferenced private artifacts, and soft-deleted documents at least 30 days old using controlled identifiers only.
- Execution revalidates under the shared lifecycle guard and document/version/job lock order, returns expired work to bounded retry or terminal failure, marks invalid-artifact versions failed, and quarantines orphans.
- Every mutation writes an actor-attributed controlled critical audit event. Audit failure rolls database mutation back and restores an orphan from quarantine.
- Inventory follows private-root containment, strict ACL, reparse rejection, and replacement-lock controls. No broad recursive delete or automatic purge is permitted.

Physical purge is deliberately report-only pending an operational backup checkpoint and separate explicit purge execution design.
