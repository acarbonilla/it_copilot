# IC-014 Specification - Document Management API

**Feature:** F-03 Documentation Management
**Batch:** D
**Baseline:** `cac7285a1296de03b0f7967af2b6691b50744871`

## Contract

- Session-authenticated `/api/v1/documents` endpoints provide bounded list/detail/status, multipart upload, optimistic metadata update, attachment download, archive, restore, soft delete, and explicit failed/cancelled candidate retry.
- Lists default to 25 and cap at 100, use deterministic created/title ordering, permit active/archived and policy-bounded owner filters, and never search content.
- Owners see only their documents; `IT_DOC_ADMIN` sees all; App Admin-only users see non-content operational fields and no title, description, filename, download, or mutation capability. Inactive and anonymous identities are denied.
- Mutations require CSRF and expected metadata revision. Cross-owner, missing, and deleted direct identifiers return the same generic not-found response.
- Downloads reauthorize the parent document, verify stored digest and size, stream the original as an attachment, and set `nosniff` plus `private, no-store`.
- Retry locks document, version, and job state, permits only the failed/cancelled candidate of an active document, prevents duplicate nonterminal jobs, and records its controlled critical audit event atomically.

No extracted-text endpoint, inline preview, content search, recovery command, or F-04 behavior is introduced.
