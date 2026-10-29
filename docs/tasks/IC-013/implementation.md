# IC-013 Implementation Record

**Batch C implementation commit:** `6b2d3fd75f5e729c7d3b487c3b74d657fe1dd8b8`

## Implementation

- `documents.extraction_worker` performs bounded parsing and writes an exclusive private UTF-8 result.
- `documents.extraction_isolation` establishes Job Object containment before sending the parse handshake, refreshes the database lease during long work, terminates the entire job on deadline/lease loss, and accepts only bounded structured metadata.
- `documents.processor` verifies original digest/length, invokes isolation, verifies staged output digest/length/character count, and calls the fenced publication service.
- Successful publication creates exactly one `ExtractedTextArtifact`, marks the version ready, promotes the candidate to current, clears the candidate, and terminalizes the job in one transaction.
- Missing/corrupt originals and invalid/unsupported content fail terminally. Timeout, resource exhaustion, parser infrastructure failure, and database interruption use bounded retries.
- `process_documents` reports only `document_job outcome=<controlled> count=<integer>`.

## Private-content assumptions

Extracted and staged text is document content. The Windows storage trust assumptions documented by IC-011 apply unchanged: the service identity and SYSTEM are the only explicit root DACL principals; service-controlled non-reparse ancestors, Windows, administrators, and the service process are trusted. Database backup and private-root backup must be treated as one consistency set. External malware scanning remains outside the local MVP.
