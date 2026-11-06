# IC-015 Specification - Document Management User Interface

**Feature:** F-03 Documentation Management
**Batch:** D
**Baseline:** `cac7285a1296de03b0f7967af2b6691b50744871`

## Contract

- `/documents` restores the session before rendering authorized data and supports list/filter/pagination, one-file PDF/TXT/Markdown upload, metadata editing, status, attachment download, archive/restore, soft delete, and retry.
- Controls render from server-provided capabilities. App Admin-only users receive an operational view without upload, content metadata, download, or mutation controls.
- Client file checks are usability-only; server validation remains authoritative. Destructive lifecycle actions require confirmation and stale conflicts display a safe error.
- Queued/staged/processing rows poll only while present and browser-visible, at a five-second interval; polling never creates work.
- No document content, storage key/path, job lease, token, or sensitive response is persisted in browser storage, URL parameters/fragments, analytics, or console output.

The UI adds no inline preview, extracted-text rendering, content search, Batch E controls, or F-04 behavior.
