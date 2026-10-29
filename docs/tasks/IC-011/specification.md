# IC-011 - Secure Upload and Private Artifact Storage

**Status:** Product Owner ratified under the F-03 consolidated G1 baseline
**Finalized G1 specification:** `054bb5427b898a2e46eb085892d0b3f58a71b54c`
**Dependencies:** IC-009 and IC-010; F-01 session/CSRF; IC-008 audit infrastructure

## Objective

Accept one bounded PDF, UTF-8 plain-text, or UTF-8 Markdown upload into contained private local storage and atomically establish its document, immutable version, integrity metadata, queued processing job, candidate-version relationship, and controlled audit records.

## Contract

- Endpoint: authenticated, CSRF-protected `POST /api/v1/documents`, multipart only.
- Request: exactly `title`, optional `description`, and exactly one `file`; unknown fields/files are rejected.
- Limits: 12 MiB total request, 10 MiB streamed file, PDF from 1 through 500 pages.
- Formats: `.pdf` (`application/pdf` or generic binary declaration), `.txt` (UTF-8), and `.md` (UTF-8). Declared type, extension, signature/content, and PDF structure must agree.
- Reject empty, malformed, encrypted, active-content PDF, invalid UTF-8, NUL-bearing text, archive, office, executable, unsupported, or mismatched uploads.
- Storage: configured non-served private root; generated opaque keys only; exclusive file creation; no user filename in paths; no symlink/junction/reparse traversal.
- Metadata: normalized display filename, SHA-256 digest, exact byte length, and detected media type. Digest does not deduplicate or reveal cross-owner content.
- Lifecycle: initial immutable version is `QUEUED`, a single `PENDING` job is enqueued, `candidate_version` is set through the ownership guard, and `current_version` remains null until Batch C publishes a successful result.
- Atomicity: the private artifact is provisional until document/version/artifact/job/audit transaction commit. Any failure removes it or moves it to private quarantine; no database-visible usable partial document remains.

Upload responses contain only document UUID, version UUID, and safe status. They never expose filenames, digests, storage keys/paths, audit data, or parser diagnostics.

## Acceptance criteria

1. All limits, formats, content checks, authentication, ownership, role policy, CSRF, and generic errors are enforced server-side.
2. Storage rejects path traversal, invalid keys, served roots, symlink/reparse paths, collisions, and non-regular artifacts.
3. Original filenames are display metadata only; artifact paths use generated opaque identifiers.
4. Document ownership and candidate-version ownership invariants are preserved without bulk-update bypass.
5. Database creation, job enqueue, required audit, and filesystem persistence succeed as one compensated unit.
6. Disk, database, enqueue, audit, cleanup, validation, and commit failures leave no usable partial document; failed deletion uses private quarantine for later reconciliation.
7. Native Windows filesystem, native MySQL, API/CSRF, concurrency regression, migration/drift, and complete backend suites pass.

## Exclusions

Text extraction, job claiming/retries/leases, parser-process isolation for extraction, result publication, download/list/detail APIs, frontend UI, purge/reconciliation commands, and F-04 retrieval remain later tasks.
