# IC-007 — Implementation

**Status:** Implemented on `task/IC-007-app-admin-user-lifecycle`; SOL G2 review pending
**Base:** `33db61b5cfb1e99d4dcff7719bd3a788cf572b43`
**Environment:** Windows 11, PowerShell, Python virtualenv, Django 5.2.7, native MySQL, Node/npm, Next.js 16.4.3
**Updated:** 2026-10-28

## Delivered scope

- Added durable `DEACTIVATED` state, singleton row-lock guard, and non-destructive deletion-review record.
- Added active App Admin-only paginated list/detail/PATCH/deactivate/reactivate/deletion-review APIs. PATCH accepts only `it_role` and `is_app_admin`.
- Reused the IC-006 invitation endpoint. No registration or direct active-account creation route was added.
- Deactivation removes every database session decoded as belonging to the target inside the mutation transaction. Reactivation never recreates a session.
- Last-admin-affecting operations lock one shared guard row before locking/counting users. Native MySQL concurrent deactivation proves one operation succeeds and one is protected.
- Extended the IC-008 database action constraint by forward migration; successful mutations and audit events commit atomically.
- Added `/admin/users` with invitation, role/App Admin edits, explicit lifecycle confirmations, and deletion-review initiation.

## Security and limitations

Serialization is a six-field allowlist. Audit records contain only controlled vocabulary and opaque actor/target IDs. Injected audit failure rolls back user and session mutations. Django sessions do not index user ID, so revocation decodes the bounded MVP session table (O(total sessions)). Requests beginning after commit are denied immediately; an already executing request cannot be recalled. Deletion execution and cleanup remain IC-024 scope.

Verified implementation commit: `0fd44e949a069be9a081f7f9b650b67094be8191`. The final draft PR head is recorded in the PR and delivery report because a commit cannot embed its own SHA.
