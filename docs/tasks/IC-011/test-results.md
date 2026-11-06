# IC-011 Test Results

**Environment:** Windows local MVP, Python 3.13 virtual environment, Django 5.2.7, pypdf 6.21.4, native MySQL
**Executed during Batch B:** Yes

SOL review `5695041394` required PDF isolation, a verified filesystem mutation boundary, and pre-parse handling of invalid request lengths. The remediation tests below are newly executed against the replacement head.

| Command | Result |
| --- | --- |
| `manage.py test documents --settings=config.settings.test -v 1` | PASS - 47 tests; native-MySQL concurrency test intentionally skipped |
| `manage.py migrate` | PASS - document 0003 and audit 0006 applied |
| `manage.py migrate --check` | PASS |
| `manage.py makemigrations --check --dry-run` | PASS - no model drift |
| `manage.py test documents -v 1` | PASS - 47/47 native MySQL, including concurrency, Windows junction, ACL, replacement-lock, PDF-isolation, and request-boundary tests |
| First `manage.py test -v 1` | Expected guardrail failure only - new authorized route absent from exact URL inventory |
| Final `manage.py test -v 1` | PASS - complete 170/170 native MySQL backend suite after security remediation (203.698 seconds) |
| `python -m pip check` | PASS - no broken requirements |
| `manage.py check` | PASS |
| `npm run validate` | PASS - structure and example-secret checks |
| `git diff --check origin/main..HEAD` | PASS |

## Security and failure evidence

- Accepted PDF/TXT/Markdown; duplicate bytes create distinct documents and opaque keys.
- Rejected malformed signature/structure, encryption, PDF active action, configured page-limit breach, invalid UTF-8, NUL text, archive extension, and declared-type mismatch.
- Streamed limit removes partial file; total request middleware returns generic 413 before body parsing.
- Authentication, CSRF, App Admin-without-IT-role denial, exact field/file allowlist, and safe response shape pass.
- Real Windows directory junction escaping outside the private root is rejected.
- Traversal/filename storage keys and storage beneath a served public root are rejected.
- Disk write, artifact-row creation, job enqueue, and required-audit failures leave no document/version/artifact/job/file.
- Cleanup failure moves the uncommitted artifact into private quarantine with no database reference.
- Partial-write cleanup failure also moves the artifact into private quarantine before propagating the original validation failure.
- Candidate version belongs to its document and current version remains null.
- Audit events contain document UUID and controlled vocabulary only; response contains no filename, digest, storage key, or path.
- The PDF child does not parse before Job Object assignment/handshake. Timeout termination, 128 MiB test-budget exhaustion, malformed PDF rejection, deliberate child failure, and valid child completion are covered.
- The Windows private-root ACL contains exactly the service SID and SYSTEM as explicit allow entries. Injecting an Everyone full-control ACE is detected, and an open non-delete-sharing root handle prevents rename/replacement.
- Missing, nonnumeric, zero, negative, and oversized `Content-Length` values are rejected by middleware without invoking the downstream handler or accessing the request body.

## Limits of this evidence

Batch B validates PDF structure in a Windows Job Object subprocess with the ratified 120-second/512 MiB preflight ceiling. Batch C still owns extraction-worker leases, independent extraction subprocess orchestration, normalized result creation, and fenced publication. Uploaded artifacts are private and non-executable, but the local MVP does not claim antivirus certification or external malware scanning.
