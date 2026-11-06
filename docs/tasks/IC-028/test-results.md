# IC-028 Test Results

**Local date:** 2026-11-06
**Environment:** Windows project virtual environment; SQLite test settings and configured native MySQL test database.

| Check | Result |
| --- | --- |
| Focused IC-028 lifecycle, processor, reconciliation, storage, inventory, and migration tests | PASS — 55 tests, 0 skips (73.871 seconds) |
| Relevant SQLite inventory/reconciliation/storage/jobs/uploads/processor/migration regressions | PASS — 72 tests, 9 expected platform/database skips (88.995 seconds) |
| Native MySQL processing-job plus reconciliation concurrency suite | PASS — 10 tests, 0 skips (21.961 seconds) |
| Publication-first invalid-artifact race | PASS — 1 test, 0 skips (3.713 seconds) |
| Reconciliation-first invalid-artifact race | PASS — 1 test, 0 skips (3.753 seconds) |
| `makemigrations --check --dry-run` | PASS — no changes detected |
| `manage.py check` | PASS — no issues |
| Python compile check | PASS |

Focused evidence covers missing original references; missing/corrupt original and extracted files; size/digest mismatch; original/extracted tombstones; success- and failure-audit rollback; duplicate publication fencing; invalid-current recovery and rollback; referenced-file preservation; unavailable cleanup database; and a 257-row assessment crossing the 256-row batch boundary without mutation.

Native MySQL evidence uses row locks and controlled thread events/barriers rather than sleep-based ordering. It covers competing claims and publication/quarantine winner order while executing the new guarded artifact validation and success audit.

The targeted AC-07 evidence adds two same-document/version races. Publication-first holds the publication transaction during its success audit; the reconciliation thread is observed incomplete until release, then returns `already_reconciled` because both committed artifacts remain valid. Final state is READY/current/SUCCEEDED with one extracted reference, both files present, exactly one processing-success audit, and no failure or reconciliation audit. Reconciliation-first holds document/version rows during validation of a corrupted original; publication is observed incomplete until release, then is lease-fenced. Final state is FAILED/not-current/job-FAILED with no extracted reference or success audit, exactly one processing-failure and one reconciliation audit, and guarded compensation deletes the unreferenced extracted file.

Commands were run from `apps/api`:

```powershell
$env:DJANGO_SETTINGS_MODULE='config.settings.test'
..\..\.venv\Scripts\python.exe manage.py test documents.tests.test_jobs.ProcessingJobLifecycleTests documents.tests.test_processor.DocumentProcessorTests documents.tests.test_reconciliation.DocumentReconciliationTests documents.tests.test_storage.PrivateArtifactStoreTests documents.tests.test_inventory.BoundedArtifactInventoryTests documents.tests.test_migrations

..\..\.venv\Scripts\python.exe manage.py test documents.tests.test_inventory documents.tests.test_reconciliation documents.tests.test_storage documents.tests.test_jobs documents.tests.test_uploads documents.tests.test_processor documents.tests.test_migrations

Remove-Item Env:DJANGO_SETTINGS_MODULE -ErrorAction SilentlyContinue
..\..\.venv\Scripts\python.exe manage.py test documents.tests.test_inventory.InventoryKeysetMySQLTests documents.tests.test_reconciliation.ArtifactQuarantineConcurrencyTests documents.tests.test_jobs.ProcessingJobConcurrencyTests --noinput

..\..\.venv\Scripts\python.exe manage.py test documents.tests.test_reconciliation.ArtifactQuarantineConcurrencyTests.test_publication_wins_against_invalid_artifact_reconciliation --noinput
..\..\.venv\Scripts\python.exe manage.py test documents.tests.test_reconciliation.ArtifactQuarantineConcurrencyTests.test_invalid_artifact_reconciliation_wins_against_publication --noinput
..\..\.venv\Scripts\python.exe manage.py test documents.tests.test_jobs.ProcessingJobConcurrencyTests documents.tests.test_reconciliation.ArtifactQuarantineConcurrencyTests --noinput

$env:DJANGO_SETTINGS_MODULE='config.settings.test'
..\..\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
..\..\.venv\Scripts\python.exe manage.py check
..\..\.venv\Scripts\python.exe -m compileall -q documents security_audit
```
