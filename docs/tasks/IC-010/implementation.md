# IC-010 Implementation Record

**Batch:** F-03 Batch A
**Implementation commit:** Pending Batch A commit creation

## Implementation

- Added a typed `DocumentCapability` vocabulary and immutable authorization decision result.
- Added one active-identity predicate that requires authentication, `is_active`, active lifecycle state, and a known IT role.
- Added direct-object authorization and owner-scoped/admin-wide queryset filtering.
- Kept App Admin operational metadata capability separate from every document content/lifecycle capability.
- Enforced policy before mutations and revalidated after acquiring the document row lock.
- Recorded sensitive authorization denials through the established controlled, best-effort denial audit path.

No frontend-hidden-control assumption is used. Later APIs, downloads, extracted-text reads, and worker triggers must consume this policy rather than reimplement role logic.
