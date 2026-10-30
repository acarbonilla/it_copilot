# IC-014 Implementation Record

## Implementation

- `documents.views` is a thin DRF adapter over the Batch A-C authorization, lifecycle, upload, storage, and job services.
- Response serializers expose only bounded metadata and server-computed capabilities. App Admin operational payloads omit all unrestricted document metadata.
- `retry_document_processing()` implements guarded explicit retry and `document.retry_requested` extends the controlled audit vocabulary through forward migration `security_audit.0007`.
- Download resolves only an opaque stored key after authorization and validates SHA-256 and byte length before returning a private attachment response.
- Routes cover collection, detail, status, download, archive, restore, delete, and retry under `/api/v1/documents`.

## Failure behavior

Validation is generic, stale revisions and invalid lifecycle/retry state return conflict, direct-object authorization is non-oracular, critical audit failure rolls mutation transactions back, and storage identifiers or parser diagnostics never enter responses.
