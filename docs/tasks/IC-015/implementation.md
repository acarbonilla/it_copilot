# IC-015 Implementation Record

## Implementation

- `DocumentsManager` provides the responsive accessible management view and uses the existing credentialed API/CSRF client.
- Multipart requests omit a caller-supplied content type so the browser supplies its boundary; CSRF bootstrap/retry behavior matches existing unsafe JSON requests.
- Download uses a normal authorized attachment link. Metadata and lifecycle operations refresh the bounded current page after success.
- The server-side download remediation is transparent to the UI: the attachment link receives a stream tied to one verified server handle, with no client buffering or browser persistence added.
- Five-second visibility-gated polling is limited to rows in staged, queued, or processing state and is cleared when no longer needed.
- Dashboard navigation exposes the available Documents module while retaining the existing App Administration separation.

No browser persistence or document-content logging is present.
