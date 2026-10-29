# IC-011 Test Results

**Environment:** Windows local MVP, Python 3.13 virtual environment, Django 5.2.7, pypdf 6.21.4, native MySQL
**Executed during Batch B:** Yes

| Command | Result |
| --- | --- |
| `manage.py test documents --settings=config.settings.test -v 1` | PASS - 38 tests; native-MySQL concurrency test intentionally skipped |
| `manage.py migrate` | PASS - document 0003 and audit 0006 applied |
| `manage.py migrate --check` | PASS |
| `manage.py makemigrations --check --dry-run` | PASS - no model drift |
| `manage.py test documents -v 1` | PASS - 38/38 native MySQL, including concurrency and Windows junction test |
| First `manage.py test -v 1` | Expected guardrail failure only - new authorized route absent from exact URL inventory |
| Final `manage.py test -v 1` | PASS - complete 161/161 native MySQL backend suite after route inventory correction and final cleanup-hardening test |
| `python -m pip check` | PASS - no broken requirements |
| `manage.py check` | PASS |
| `npm run validate` | Pending final repository evidence commit |
| `git diff --check origin/main..HEAD` | Pending final repository evidence commit |

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

## Limits of this evidence

Batch B validates PDF structure in the request process after the hard 10 MiB request-file bound. Enforced Windows Job Object isolation, 120-second extraction deadline, 512 MiB ceiling, worker leases, and parser result publication remain mandatory Batch C work. Uploaded artifacts are private and non-executable, but the local MVP does not claim antivirus certification or external malware scanning.
