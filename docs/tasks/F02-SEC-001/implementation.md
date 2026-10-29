# F02-SEC-001 — Implementation

**Date:** 2026-10-29  
**Branch:** `fix/f02-sec-001-activation-token-exposure`

## Implemented design

- `/activate` remains statically rendered and passes no secret through server-component props. `ActivationBootstrap` reads `location.hash` in a layout effect, immediately calls `history.replaceState(..., "/activate")`, validates the exact 43-character token shape, and only then renders the form.
- The dynamic route was deleted. Next.js `proxy.ts` returns a constant 404 body for `/activate/:legacyToken+`; its matcher never renders the original path. Development incoming-request logging ignores those legacy paths to prevent CLI reflection. `/activate` also receives `Referrer-Policy: no-referrer`.
- `AccountInvitation.delivery_format` records `LEGACY_PATH` or `FRAGMENT_V1`. The forward migration adds the field with a temporary legacy default for existing rows, then changes the model/database default to fragment v1.
- `remediate_legacy_invitations --actor-id <id>` reports candidates only. `--execute` processes the captured IDs one at a time. Each transaction locks `AdminLifecycleGuard`, re-locks and revalidates the actor, locks the target user and invitation, revokes the legacy row, and records nonsecret actor/UUID audit events.
- Valid pending invitations receive a fresh random token and TTL, digest-only database row, and exclusive development delivery artifact. Expired, active, consumed, revoked, or otherwise ineligible legacy rows never receive a replacement.
- Artifact creation occurs inside the database transaction. Partial write cleans itself; audit/delivery/commit exceptions roll back rows and audit events, and the outer compensation removes a completed artifact after commit failure.

## Operational procedure

First run the command without `--execute`, retain the count, verify the actor ID and environment, then obtain a separate operational go-ahead before execution against any non-test database. Re-running is safe: remediated rows no longer match, and a raced captured ID returns `already_remediated` after lock-time revalidation.

## Limitations

- The development file sink remains intentionally DEBUG-only; Windows ACL guarantees remain host-dependent.
- Database and filesystem commits cannot be one atomic resource transaction; tested compensation covers application-visible failures, but an abrupt process/host loss can require artifact reconciliation.
- Development logging suppression is specific to legacy activation paths. Infrastructure in front of Next.js must independently avoid logging sensitive URLs.
- Fragment secrecy still depends on controlling browser extensions and same-page scripts; no token is placed in local/session storage.
