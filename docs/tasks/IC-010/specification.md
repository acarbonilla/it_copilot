# IC-010 - Document Authorization and Ownership

**Status:** Product Owner ratified under the F-03 consolidated G1 baseline
**Finalized G1 specification:** `054bb54c8183e3e62e9d32686492375c0e3f35e3`
**Dependencies:** IC-003, IC-007, IC-008, and IC-009

## Objective

Enforce one deny-by-default document policy for services and querysets, including immutable personal ownership, cross-owner `IT_DOC_ADMIN` authority, immediate inactive-user denial, and App Admin separation from document content.

## Authorization matrix

| Actor | Own metadata/content/lifecycle | Other users' metadata/content/lifecycle | Operational metadata |
| --- | --- | --- | --- |
| `IT_MEMBER` | Allow | Deny | Deny |
| `IT_EDITOR` | Allow | Deny | Deny |
| `IT_DOC_ADMIN` | Allow | Allow | Deny unless also App Admin |
| App Admin only | Deny | Deny | Allow |
| App Admin plus IT role | Per IT role only | Per IT role only | Allow |
| Inactive, deactivated, anonymous, unknown role | Deny | Deny | Deny |

Deleted documents are denied through normal content/metadata policy for every role. Archived documents remain policy-visible to their owner and `IT_DOC_ADMIN`, while later API/UI tasks determine which operations are exposed.

## Acceptance criteria

1. A shared policy enumerates operational metadata, view metadata, create, edit, content view, download, process, archive, restore, and delete capabilities.
2. Owners with `IT_MEMBER` or `IT_EDITOR` may operate only on their own documents; `IT_DOC_ADMIN` may manage all non-deleted documents.
3. App Admin alone has no content, download, edit, process, or lifecycle capability. Combining App Admin with an IT role grants only that IT role's document rights.
4. Query filtering and direct-object authorization produce the same owner/admin boundary and always exclude deleted documents.
5. Inactive/deactivated identities are denied on the next policy evaluation.
6. Cross-owner and App Admin-only sensitive mutation denials use generic permission errors and controlled best-effort denial audit records without document text/title/path.
7. The full matrix and audit behavior are covered by executable tests.
