# IC-014 Implementation Record

## Implementation

- `documents.views` is a thin DRF adapter over the Batch A-C authorization, lifecycle, upload, storage, and job services.
- Response serializers expose only bounded metadata and server-computed capabilities. App Admin operational payloads omit all unrestricted document metadata.
- `retry_document_processing()` implements guarded explicit retry and `document.retry_requested` extends the controlled audit vocabulary through forward migration `security_audit.0007`.
- Download resolves only an opaque stored key after authorization, opens one protected binary handle, validates SHA-256 and byte length through that handle, rewinds it, and streams that same verified handle. A response-owned wrapper closes both the handle and `PrivateArtifactStore` root-replacement lock on completion or disconnect; every pre-response error closes both immediately.
- Routes cover collection, detail, status, download, archive, restore, delete, and retry under `/api/v1/documents`.

## Failure behavior

Validation is generic, stale revisions and invalid lifecycle/retry state return conflict, direct-object authorization is non-oracular, critical audit failure rolls mutation transactions back, and storage identifiers or parser diagnostics never enter responses.

The SOL G2 secure-download remediation removes the verify-then-reopen path race. Private-root ACL/reparse validation and the replacement lock remain held from resolution through streaming completion. Concurrent archive/delete cannot substitute bytes into an already verified handle; a later deleted-document request is denied before storage is opened.
