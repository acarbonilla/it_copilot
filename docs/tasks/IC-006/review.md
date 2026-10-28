# IC-006 review

**Status:** Ready for SOL G2 exact-head review
**Date:** 2026-10-28
**Implementation commit:** `dfcb77c281480154ac1a7c10cd631e6e182fb16e`
**Draft PR:** #14 targeting `feature/identity-administration`
**Final documentation/head commit:** Supplied in the draft PR and handoff because a commit cannot contain its own SHA

## Review checklist

- Branch started exactly at `origin/feature/identity-administration` merge `726edee0312a6ad5522c1bf1aa08936477386336`; merged IC-008 commit ancestry was verified before work.
- Authorization checks use active authenticated App Admin status independently of IT role, with no client-side authorization dependency.
- Pending identity, unusable password, digest-only token storage, 24-hour expiry, single use, explicit reissue, and conflict boundaries match the approved specification.
- Activation uses MySQL row locks; a native two-thread test proves one winner.
- Password minimum and all configured Django validators run before mutation.
- Invalid activation response and logs are generic; raw secrets appear only in the explicitly enabled local mailbox and browser/API activation flow.
- Success auditing is fail-closed and atomic. Denied auditing occurs outside failed transactions through IC-008's bounded autocommit service.
- Session/CSRF conventions and structured API errors are preserved; activation does not log in.
- Frontend route uses `no-referrer`, no third-party assets, CSRF, safe errors, and history replacement to login.
- No IC-007, IC-024, vault, deployment, audit-viewing/retention, or unrelated route exists.

## SOL focus areas

1. Confirm the invitation lifecycle default for pre-existing inactive accounts is the desired safe bridge to IC-007.
2. Review the local file delivery trust boundary and mandatory Windows ACL/operator cleanup limitation.
3. Confirm the token-in-path access-log risk is acceptable for local MVP and remains a deployment gate.
4. Review MySQL locking, audit-failure rollback, reissue serialization, and delivery artifact cleanup behavior.
5. Confirm the IC-008 forward vocabulary migration and sanitized target semantics.

## Unresolved risks

- Local raw-token artifact confidentiality depends on developer host controls and cleanup.
- Future reverse proxies/access logs must redact activation paths before hosted use.
- File delivery has no retry/durability protocol beyond fail-closed local creation.
- Direct database operators remain outside application controls.
- CI, external delivery, retention, IC-007 lifecycle administration, and IC-024 deletion remain pending separate work and authorization.
