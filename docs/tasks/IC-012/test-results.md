# IC-012 Test Results

**Environment:** Windows local MVP, Django 5.2.7, native MySQL
**Executed during Batch C:** Yes

| Evidence | Result |
| --- | --- |
| Fast focused document suite | PASS - 71 tests; four native-only concurrency tests intentionally skipped |
| Native MySQL focused document suite | PASS - 71/71 (66.042 seconds) |
| Competing claimants | PASS - one attempt claimed exactly once |
| Competing completion | PASS - one result accepted; stale completion fenced |
| Expired lease and stale owner | PASS - reclaim increments attempt; prior owner rejected |
| Retry exhaustion | PASS - delays 5/30 seconds; third failure terminal |
| Archive/completion race | PASS - document ends archived with no active stale exposure |
| Cancellation and audit rollback | PASS - cancellation fences completion; audit failure restores running state |
| Publication rollback | PASS - database failure preserves prior aggregate and removes staging output |
| Complete native MySQL backend suite | PASS - 194/194 (200.499 seconds) |
| Migration apply/check and model drift | PASS - `0004` and `0005` applied; no pending migration or model drift |
| Dependency and Django checks | PASS - `pip check` and `manage.py check` |
| Repository structure validation | PASS |
| `git diff --check origin/main..HEAD` | PASS |
