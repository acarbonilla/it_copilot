# F-03 Final Acceptance Review

**Status:** Submitted for final SOL G2; PO acceptance pending

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
