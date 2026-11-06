# IC-027 Test Results

**Local date:** 2026-11-05
**Environment:** Project virtual environment on Windows; SQLite regression settings and configured native MySQL test database.

| Check | Result |
| --- | --- |
| `manage.py test documents.tests.test_inventory` | PASS — 12 tests, 1 native-MySQL skip (22.015 seconds) |
| Relevant inventory/reconciliation/storage/job/upload/processor SQLite suites | PASS — 60 tests, 9 platform/database skips (94.495 seconds) |
| Native MySQL inventory keyset plus IC-026 concurrency suites | PASS — 9 tests (18.207 seconds) |
| `makemigrations --check --dry-run` | PASS — no changes detected |
| `manage.py check` | PASS — no issues |

Evidence covers cap-plus-one stopping with an instrumented scanner, work exhaustion, cursor tamper/expiry/actor/root rejection, stable multi-page coverage, insertion/deletion invalidation, referenced original/extracted classification, filesystem/database failure, observational behavior, 256-row native-MySQL keyset boundaries, and unchanged IC-026 concurrency behavior.

Commands used:

```powershell
$env:DJANGO_SETTINGS_MODULE='config.settings.test'
..\..\.venv\Scripts\python.exe manage.py test documents.tests.test_inventory
..\..\.venv\Scripts\python.exe manage.py test documents.tests.test_inventory documents.tests.test_reconciliation documents.tests.test_storage documents.tests.test_jobs documents.tests.test_uploads documents.tests.test_processor

Remove-Item Env:DJANGO_SETTINGS_MODULE -ErrorAction SilentlyContinue
..\..\.venv\Scripts\python.exe manage.py test documents.tests.test_inventory.InventoryKeysetMySQLTests documents.tests.test_reconciliation.ArtifactQuarantineConcurrencyTests documents.tests.test_jobs.ProcessingJobConcurrencyTests --noinput

$env:DJANGO_SETTINGS_MODULE='config.settings.test'
..\..\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
..\..\.venv\Scripts\python.exe manage.py check
```
