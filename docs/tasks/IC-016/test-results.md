# IC-016 Test Results

**Environment:** Windows 11, Django 5.2.7, native MySQL, private NTFS storage

| Evidence | Result |
| --- | --- |
| Focused reconciliation/storage/upload suite | PASS - 21/21 (44.298 seconds) |
| Dry-run leaves orphan unchanged | PASS |
| Explicit execution quarantines orphan and audits | PASS |
| Audit failure restores quarantined artifact | PASS |
| Expired lease returns to bounded retry idempotently | PASS |
| Missing artifact failure and audit rollback | PASS |
| Invalid/non-App-Admin actor denial | PASS |
| ACL verify-first/enforce-if-needed and reparse checks | PASS in storage plus real-worker acceptance |
| Complete native MySQL backend suite | PASS - 208/208 (263.044 seconds) exact-head rerun |

No live non-test reconciliation or physical purge was performed.
