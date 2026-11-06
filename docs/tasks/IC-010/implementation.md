# IC-010 Implementation Record

**Batch:** F-03 Batch A
**Implementation commit:** `494973c3ed493ce4b484dd819f41a3c9fa4f5277`
**SOL G2 remediation commit:** `bfcb5f7f9734a579d4089ec8142a835a990d30f4`

## Implementation

- Added a typed `DocumentCapability` vocabulary and immutable authorization decision result.
- Added one active-identity predicate that requires authentication, `is_active`, active lifecycle state, and a known IT role.
- Added direct-object authorization and owner-scoped/admin-wide queryset filtering.
- Kept App Admin operational metadata capability separate from every document content/lifecycle capability.
- Enforced policy before mutations and revalidated after acquiring the document row lock.
- Recorded sensitive authorization denials through the established controlled, best-effort denial audit path.

No frontend-hidden-control assumption is used. Later APIs, downloads, extracted-text reads, and worker triggers must consume this policy rather than reimplement role logic.

## SOL G2 remediation

- Replaced pre-lock direct lookup with one transactional `SELECT ... FOR UPDATE` resolution and authorization path.
- Missing, deleted, cross-owner, deactivated, and role-downgraded access all raise the same `DocumentUnavailableError` with the same generic message.
- Actor state is reloaded from the database for each operation so a stale in-memory user cannot retain rights after deactivation or role downgrade.
- Unavailable-attempt audit records deliberately omit the supplied document identifier. They record the controlled action, actor snapshot where available, `it_document` target type, and denied outcome without revealing whether the probed UUID exists.
- Authorized operations retain expected-revision checks and critical audit writes inside the locked mutation transaction.
