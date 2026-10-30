# IC-013 Test Results

**Environment:** Windows local MVP, Python 3.13, pypdf 6.21.4, native MySQL
**Executed during Batch C:** Yes

| Evidence | Result |
| --- | --- |
| Fast focused document suite | PASS - 71 tests; four native-only concurrency tests intentionally skipped |
| Native MySQL focused document suite | PASS - 71/71 (66.042 seconds) |
| Real isolated PDF/TXT/Markdown extraction | PASS |
| UTF-8/newline normalization and 2,000,000-character ceiling | PASS |
| Job Object timeout and process-tree termination | PASS |
| Job memory exhaustion and subprocess failure | PASS |
| Heartbeat/lease loss termination | PASS |
| Missing and digest-corrupt originals | PASS - terminal, no result |
| Staged-output integrity and publication failure cleanup | PASS |
| Synthetic secret/filename/path worker-log scan | PASS |
| Complete native MySQL backend suite | PASS - 194/194 (200.499 seconds) |
| Migration apply/check and model drift | PASS - `0004` and `0005` applied; no pending migration or model drift |
| Dependency and Django checks | PASS - `pip check` and `manage.py check` |
| Repository structure validation and diff whitespace | PASS |

## SOL G2 concurrency follow-up

The IC-012 native MySQL locked-earliest-document regression initially failed on the Batch C exact head and passes after the claim scan correction. IC-013 processing behavior is unchanged except that an available later job can now be reached; the full extraction and publication regressions are covered by the 72-test document suite and 195-test backend suite.

| Follow-up evidence | Result |
| --- | --- |
| `manage.py test documents.tests.test_jobs -v 1 --noinput` | PASS - 10/10 (2.394 seconds) |
| `manage.py test documents -v 1 --noinput` | PASS - 72/72 (38.510 seconds) |
| `manage.py test -v 1 --noinput` | PASS - 195/195 (211.162 seconds) |
