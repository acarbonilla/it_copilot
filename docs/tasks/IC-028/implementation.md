# IC-028 Implementation Record

## Production changes

- `documents.jobs`: validates both artifacts under the IC-026 guard and locked claim; atomically records processing-success; critically audits terminal worker failures and cancellations.
- `documents.storage`: adds bounded 64 KiB streaming size/SHA-256 validation through the existing private-path resolver.
- `documents.processor`: replaces blind cleanup with guarded, reference-aware compensation and raises a controlled unresolved-cleanup error when reference state is uncertain.
- `documents.reconciliation`: clears an invalid current pointer in the same transaction as version/job failure and reconciliation audit; unrelated current pointers and retry candidates are preserved.
- `documents.inventory`: adds bounded, signed-cursor historical READY/current assessment.
- `assess_document_consistency`: exposes the assessment as an App-Admin-only read-only command with limit, work budget, cursor, and optional physical checking.
- `security_audit`: adds controlled `document.processing_succeeded` and `document.processing_failed` actions through forward migration `0009_alter_securityauditevent_action`.

Publication retains the guard → document → version → job order. Authoritative integrity validation occurs inside the publication transaction after locks are acquired. The extracted file remains a filesystem resource outside database rollback; guarded compensation handles failed or ambiguous publication.

## Scope decisions

No database trigger or filesystem I/O migration was added. Direct SQL and permanent post-transition filesystem availability remain outside the service-level guarantee. Retry-wait transitions are not audited under the approved policy. No IC-026/IC-027 coordination semantics, frontend, external service, or deployment architecture was changed.

## G2 targeted concurrency evidence

`ArtifactQuarantineConcurrencyTests` now includes two native-MySQL-only tests in `documents/tests/test_reconciliation.py`:

- `test_publication_wins_against_invalid_artifact_reconciliation` holds publication inside its critical success audit after the guard and document/version/job locks are acquired. Invalid-artifact reconciliation starts on a separate connection, blocks on the document row, and then revalidates the now-published healthy artifacts as `already_reconciled` after publication commits.
- `test_invalid_artifact_reconciliation_wins_against_publication` corrupts the original, holds reconciliation during artifact validation after document/version locks are acquired, and starts publication on a separate connection. Publication blocks, reconciliation commits FAILED/job failure/current clearing plus both required failure/reconciliation audits, and publication resumes only to be lease-fenced. The remaining unreferenced extracted file is removed through guarded `_compensate_extracted()`.

Both tests propagate thread exceptions, use finite `threading.Event` waits, confirm the loser cannot complete while the winner holds the conflicting rows, and assert exact document/version/job/reference/audit/physical outcomes. No production code was changed for these tests.
