# IC-011 Implementation Record

**Batch:** F-03 Batch B
**Implementation commit:** Pending Batch B commit creation

## Implementation

- Added pinned `pypdf==6.21.4` for strict PDF structural validation, encryption detection, active-content checks, and page counting.
- Added the one-to-one `OriginalArtifact` integrity model and forward migration.
- Added `document.upload_created` to the controlled audit vocabulary through a forward migration.
- Added `PrivateArtifactStore` with an explicit private root, opaque keys, SHA-256 streaming, exact length, exclusive `0600` file creation, containment checks, served-root rejection, and symlink/reparse detection.
- Added removal-then-quarantine compensation. Quarantine remains under the private root and has no database/document reference.
- Added the atomic upload service: revalidate actor, persist/validate provisional artifact, create document/version/artifact/job, set guarded candidate version, write both critical audit events, and commit.
- Added pre-CSRF request-size middleware so oversized multipart bodies are rejected before multipart/CSRF parsing.
- Added the narrow multipart upload endpoint with session authentication, CSRF, exact field/file allowlist, safe responses, and generic failures.
- Updated the approved URL inventory and local `.env.example` private-root setting.

No public media/static serving configuration was introduced. There is no artifact download or content-rendering route in Batch B.

## Migrations

- `documents/0003_originalartifact.py`
- `security_audit/0006_remove_securityauditevent_audit_action_known_and_more.py`

Django generated the audit migration name while replacing the controlled action constraint; all prior actions remain present.

## Compensation order

1. Write a generated opaque artifact exclusively inside the private root.
2. Validate extension, declared type, content/signature, PDF safety/page count, digest, and size.
3. Within one MySQL transaction create document, version, artifact metadata, pending job, candidate reference, and critical audit events.
4. On any exception, roll back MySQL and remove the provisional artifact.
5. If removal fails, atomically move it to private quarantine; if both operations fail, raise a reconciliation-required error while leaving no database-visible document.
