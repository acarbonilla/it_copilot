# IC-014 Test Results

**Environment:** Windows local MVP, Django 5.2.7, native MySQL

| Evidence | Result |
| --- | --- |
| Focused API/upload suite | PASS - 10/10 |
| Native MySQL document suite | PASS - 78/78 (38.966 seconds) |
| Owner isolation and cross-owner direct access | PASS |
| `IT_DOC_ADMIN` cross-owner list | PASS |
| App Admin metadata-only response/content denial | PASS |
| Inactive identity denial | PASS |
| CSRF and optimistic revision conflict | PASS |
| Retry single-job/idempotence behavior | PASS |
| Attachment disposition, integrity and security headers | PASS |
| Critical retry-audit failure rollback | PASS - no job and failed version preserved |
| Forward migration/model drift | PASS - `security_audit.0007` applied; no changes detected |
| Complete native MySQL backend suite | PASS - 201/201 (233.468 seconds) |
