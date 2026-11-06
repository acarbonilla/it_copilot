# F-03 Final Acceptance Review

**Status:** F-03 G2 PASS WITH ACCEPTED LIMITATIONS — merged to `main` through PR #22 and post-merge verified by IC-030

**Acceptance head:** `ae48121003322bc61c5e539fd5eb73b739fd201f`
**Acceptance verification date:** 2026-11-06
**Integration merge commit:** `19ea923e2698a085afac6a145fda70c7f6974b83`

PR #22 merged the accepted feature head `7bbb4c663a7daebe659e700dd0240556f6cc86ff` into `main` on 2026-11-06. IC-030 post-merge smoke verification passed; the accepted limitations below remain in force.

## IC-026 orphan quarantine remediation

The prior recovery acceptance entry did not cover the inventory-to-quarantine publication race. IC-026 adds shared database serialization, execution-time reference validation, quarantine tombstones, fail-closed audit recovery, and controlled concurrency regressions. Its original native MySQL concurrency suite passed 7 tests; IC-026-R01 adds separate lock-failure, real-upload race, and restore-failure evidence. The earlier pending-review state was closed by the consolidated F-03 G2 acceptance; the evidence remains preserved here.

## IC-027 bounded inventory remediation

IC-027 replaces full-store reconciliation enumeration with signed continuation pages, a separate 5,000-unit default work budget (10,000 maximum), 256-row database batches, and deterministic directory snapshots capped at 4,096 entries. Capacity overflow, stale/invalid cursors, and storage/database failures fail closed without claiming completion. The extracted root therefore has an explicit 4,096-version-directory MVP ceiling. Concurrent mutation follows documented forward-scan semantics rather than a point-in-time snapshot. The earlier pending-review state was closed by the consolidated F-03 G2 acceptance; PR #22 remains unauthorized for merge.

## IC-028 READY consistency remediation

IC-028 validates original and extracted physical integrity under the shared publication guard before READY/current/job-success publication, makes processing-success and terminal-failure audits critical and transactional, uses reference-aware fail-closed filesystem compensation, clears invalid current pointers during audited recovery, and adds a bounded read-only historical assessment. Local focused, SQLite regression, and native MySQL concurrency evidence passed; the consolidated F-03 G2 acceptance closed the earlier pending-review state. No merge is authorized.

Targeted IC-028 AC-07 evidence includes deterministic native MySQL publication-first and invalid-reconciliation-first races on the same document/version. Both individual tests and the resulting 10-test concurrency suite passed with zero skips; final state, artifact reference/physical cleanup, lease fencing, and exact critical audit counts are asserted. This closed the identified evidence gap before consolidated F-03 G2 acceptance.

F-03 now provides owner-isolated document lifecycle, `IT_DOC_ADMIN` cross-owner management, App Admin metadata-only separation, validated private upload/storage, deterministic processing with Windows isolation, secure same-handle downloads, the management UI, and dry-run-first recovery controls.

## Security acceptance matrix

| Boundary | Evidence | Result |
| --- | --- | --- |
| Owner/query/direct-ID authorization | policy/service/API/native suites and Chrome | PASS |
| App Admin metadata-only separation | API/UI tests and Chrome | PASS |
| Inactive/anonymous and CSRF denial | backend security regressions | PASS |
| Private upload, ACL, traversal/reparse containment | storage/upload suites and real worker | PASS |
| Job concurrency, leases, fencing, retries | native MySQL concurrency suites | PASS |
| Same-handle integrity-checked download | replacement-race and Chrome attachment tests | PASS |
| Archive/restore/delete and audit rollback | service/API/native/Chrome suites | PASS |
| Recovery dry-run, actor, idempotence, compensation | IC-016 focused suite | PASS |
| Browser/server content leakage | synthetic marker/filename scans | PASS |
| Scope boundary | source scan and task inventory | PASS |

## Residual limitations

- Local Windows/NTFS and native MySQL are the supported MVP environment; no hosted deployment or external object store was tested.
- Strict allowlisting and isolated parsing are not malware certification or antivirus scanning.
- Database and private artifact storage require a coordinated backup/restore checkpoint.
- Thirty-day physical purge is reported as eligible but is not automatically or operationally executed; quarantine is retained for explicit later disposition.
- Real-browser evidence covers TXT processing; PDF/Markdown and resource-failure variants are covered by backend isolation/unit tests.

No F-04 retrieval/AI behavior, IC-024 account deletion, production recovery execution, PR merge, or `main` merge is included.

## IC-029 consolidated functional acceptance

The consolidated review used the ratified IC-009 through IC-017 contract and the committed IC-026, IC-027, and IC-028 remediations. The repository remained on `feature/documentation-management` at `ae48121003322bc61c5e539fd5eb73b739fd201f`. The unrelated pre-existing `apps/web/next-env.d.ts` modification was preserved and was not edited by this review. Earlier sections above preserve their historical gate wording; the matrix below is the current IC-029 recommendation.

| Functional area | Disposition | Consolidated evidence |
| --- | --- | --- |
| Document authorization and owner-private WEB boundaries | Implemented and tested | Shared policy/service/API tests cover owners, IT roles, App Admin metadata-only access, inactive callers, query filtering, and direct identifiers. The ratified F-03 baseline contains no category aggregate or workflow, so category authorization is not applicable. |
| Upload validation and private storage | Implemented and tested | PDF/TXT/Markdown allowlisting, request/file/page bounds, opaque contained storage, Windows ACL/reparse controls, digest/length metadata, and compensation are covered by the complete backend suite and prior Batch B evidence. |
| Version creation, retention, and history | Implemented and tested | Replacement uploads create immutable versions; failed/cancelled replacements do not displace the last valid current version; historical access remains governed by the parent document. No separate end-user history browser was ratified. |
| Asynchronous processing and deterministic jobs | Implemented and tested | Database queue, claim/lease/heartbeat, bounded retries, cancellation, idempotence, and stale-worker fencing passed complete backend and native MySQL concurrency tests. |
| READY publication and current consistency | Implemented and tested | IC-028 guarded publication atomically validates artifacts and commits extracted reference, READY/current state, job success, and critical audit; publication/reconciliation race tests passed on native MySQL. |
| Original and extracted artifact integrity | Implemented and tested | Physical existence, size/digest, private-path containment, tombstone, and reference checks are enforced before publication and reads. |
| Failure, reconciliation, and recovery | Implemented and tested | Terminal failures are critically audited; invalid current pointers are cleared by audited recovery; compensation fails closed when restoration is uncertain. |
| Quarantine, deletion, and cleanup | Implemented with accepted limitation | Shared guard and execution-time revalidation prevent referenced artifacts from quarantine. Soft delete is immediate. Thirty-day purge remains eligibility/report-only and quarantine disposition is an operator responsibility. |
| Bounded inventory and signed cursors | Implemented and tested | IC-027 enforces a 4,096-entry directory cap, 5,000 default/10,000 maximum work units, 256-row keyset batches, signed 24-hour scope-bound cursors, and fail-closed capacity/error states. |
| Audit completeness and failure handling | Implemented and tested | Critical mutation/publication/recovery audits are transactional and fail closed; controlled identifiers and reason codes avoid content/path leakage. |
| Native MySQL concurrency and transactions | Implemented and tested | The IC-029 native suite ran 12 tests with zero skips, covering metadata revision, inventory keysets, job concurrency, and quarantine/publication races. |
| API and frontend workflows | Implemented and tested | Current frontend unit, type, and lint checks passed. API coverage is included in the complete backend suite. Real-Chrome and production-build results are retained from prior Batch D/E evidence and were not rerun for IC-029. |

### IC-029 commands and results

- SQLite/test-settings backend: from `apps/api`, `$env:DJANGO_SETTINGS_MODULE='config.settings.test'; ..\..\.venv\Scripts\python.exe manage.py test documents --noinput` — 120 tests passed, 12 skipped, 0 failures; system check reported no issues.
- Native MySQL: from `apps/api`, after removing `DJANGO_SETTINGS_MODULE`, `..\..\.venv\Scripts\python.exe manage.py test documents.tests.test_concurrency.DocumentMetadataConcurrencyTests documents.tests.test_inventory.InventoryKeysetMySQLTests documents.tests.test_jobs.ProcessingJobConcurrencyTests documents.tests.test_reconciliation.ArtifactQuarantineConcurrencyTests --noinput` — 12 tests passed, 0 skipped, 0 failures.
- Migration consistency: test settings plus `manage.py makemigrations --check --dry-run` — `No changes detected`.
- Django system check: test settings plus `manage.py check` — no issues.
- Frontend: from `apps/web`, `npm test` — 8 files and 36 tests passed; `npm run typecheck` and `npm run lint` both exited successfully.
- Working-diff whitespace: `git diff --check` produced no errors.
- An initial migration/check command was mistakenly launched from `apps/web`; Python reported that `apps/web/manage.py` did not exist. It performed no Django operation and was rerun successfully from `apps/api`.

### Defects and limitations

- Critical: none observed.
- High: none observed.
- Medium/Low: no new functional defect observed. Browser workflows and production build were not rerun at IC-029; acceptance relies on prior exact-feature evidence for those layers plus current frontend unit/type/lint verification.
- Accepted-limitation candidates: Windows/NTFS and native MySQL local-MVP boundary; no malware certification; coordinated database/artifact backup requirement; report-only physical purge and retained quarantine; real-browser coverage centered on TXT while PDF/Markdown failure and isolation variants remain backend-tested; IC-027 forward-scan semantics and extracted-root capacity ceiling.
- Deferred/out of scope: category management, inline preview, content/semantic search, OCR, external object storage/queue, production recovery execution, F-04 retrieval/AI, and IC-024 permanent account deletion.

### Recommendation

IC-026 closes the quarantine/publication race, IC-027 closes unbounded inventory traversal, and IC-028 closes READY/current and physical-artifact consistency gaps. The consolidated evidence revealed no Critical or High blocker. SOL accepted **F-03 G2 PASS WITH ACCEPTED LIMITATIONS**. This acceptance does not authorize PR #22 or any merge; a future integration decision remains with the PO.
