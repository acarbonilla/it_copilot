# IC-010 - Document Authorization and Ownership

**Status:** Product Owner ratified under the F-03 consolidated G1 baseline
**Finalized G1 specification:** `054bb5427b898a2e46eb085892d0b3f58a71b54c`
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
6. Existing cross-owner, nonexistent, deleted, deactivated, and role-downgraded document identifiers produce the same generic unavailable exception/message. Controlled best-effort denial audit records omit the supplied document identifier as well as document text/title/path, so restricted audit metadata cannot become an existence oracle.
7. The full matrix and audit behavior are covered by executable tests.
