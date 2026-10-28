# IC-007 — Implementation

**Status:** G2 findings remediated on `task/IC-007-app-admin-user-lifecycle`; SOL re-review pending
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

Serialization is a six-field allowlist. Audit records contain only controlled vocabulary and opaque actor/target IDs. Injected audit failure rolls back user and session mutations. Requests beginning after commit are denied immediately; an already executing request cannot be recalled. Deletion execution and cleanup remain IC-024 scope.

## G2 remediation

- **G2-01:** Reactivation and IC-006 activation now lock `AdminLifecycleGuard` before target rows, matching deactivation and role edits. Every active-App-Admin membership transition follows guard→target ordering. A `post_migrate` receiver restores the singleton after Django test/database flushes; the migration remains its production initializer. Native MySQL tests cover concurrent deactivation/deactivation, downgrade/downgrade, and reactivation/deactivation.
- **G2-02:** `/admin/users` maintains the current API page, exposes Previous/Next controls, disables first/last boundaries, renders empty results, and reloads the current page after invitations or mutations. Cancelled initial loads cannot overwrite later page state.
- **G2-03:** Session decoding no longer catches and ignores exceptions. Decode, scan, and deletion errors propagate out of the atomic operation, causing a generic 500 and rollback of lifecycle, session, and audit changes. A malformed signed-data row decodes as an unauthenticated empty payload and is proven unable to access protected APIs; recognized target sessions are all deleted before success.

## Residual risks

Django's database session model does not index user ID, so revocation still performs an O(total sessions) scan and decode. A corrupt row that Django safely decodes to an empty unauthenticated payload remains inert; an actual decode exception fails the whole mutation closed. The design does not log session keys, cookies, decoded contents, or session data. These are bounded local-MVP constraints, not authorization to add a new session architecture.

Original implementation commit: `0fd44e949a069be9a081f7f9b650b67094be8191`. Reviewed pre-remediation head: `75722f0e57d1b896e1a252a1216ec8f4e8609bde`. The remediation and final draft PR head are recorded after the evidence commit and in the delivery report.
