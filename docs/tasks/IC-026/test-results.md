# IC-026 Test Results

**Local date:** 2026-11-05
**Environment:** Project virtual environment; SQLite regression settings plus configured native MySQL test database.

| Check | Result |
| --- | --- |
| `makemigrations --check --dry-run` | PASS — no changes detected |
| `manage.py check` | PASS — no issues |
| Relevant SQLite regressions (reconciliation, jobs, uploads, processor, storage) | PASS — 45 tests, 7 MySQL-only tests skipped |
| Native MySQL quarantine/job concurrency suites | PASS — 7 tests |

Focused passing coverage includes referenced original rejection, referenced extracted-text rejection, critical-audit restoration/tombstone rollback, late-publication rejection, and repeated reconciliation. Controlled event-based native MySQL tests cover publication-first, quarantine-first, and concurrent original-reference creation. Timing-only sleeps are not used as proof.

## IC-026-R01 evidence remediation

- The first native `TransactionTestCase` execution exposed that Django test flushing removes the singleton row created by the data migration. Test setup now recreates guard row `pk=1` before each native concurrency test; the corrected original suite passed all 7 tests.
- A deterministic guard-lock `DatabaseError` regression verifies no storage move, tombstone, reconciliation-success audit, or reference loss.
- An audit-failure plus restore-failure regression verifies recovery reports failure and late extracted publication rejects the now-missing source artifact.
- A native MySQL race now invokes the real `create_document_upload()` production service while quarantine competes for the same artifact key.
- R01 focused SQLite run: 18 tests passed.
- R01 relevant SQLite regression run: 48 tests passed, including 8 native-MySQL-only skips.
- R01 expanded native MySQL run: 8 tests passed (the original 7 plus the real-upload race).

The recorded implementation evidence is complete. IC-026 SOL G2 review and PO acceptance remain pending, F-03 remains at G2 HOLD, and PR #22 is not authorized for merge.
