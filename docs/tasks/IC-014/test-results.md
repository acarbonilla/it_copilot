# IC-014 Test Results

**Environment:** Windows local MVP, Django 5.2.7, native MySQL

| Evidence | Result |
| --- | --- |
| Focused API/upload suite | PASS - 12/12 |
| Native MySQL document suite | PASS - 80/80 (39.576 seconds) after secure-download remediation |
| Owner isolation and cross-owner direct access | PASS |
| `IT_DOC_ADMIN` cross-owner list | PASS |
| App Admin metadata-only response/content denial | PASS |
| Inactive identity denial | PASS |
| CSRF and optimistic revision conflict | PASS |
| Retry single-job/idempotence behavior | PASS |
| Attachment disposition, integrity and security headers | PASS |
| Verify/rewind/stream same-handle path replacement regression | PASS - replacement bytes never streamed |
| Streaming and integrity-error resource closure | PASS - file/store protection resources released |
| Concurrent archive/delete and later authorization denial | PASS - open verified stream remains original; later deleted request denied before storage open |
| Critical retry-audit failure rollback | PASS - no job and failed version preserved |
| Forward migration/model drift | PASS - `security_audit.0007` applied; no changes detected |
| Complete native MySQL backend suite | PASS - 203/203 (220.973 seconds) after secure-download remediation |
