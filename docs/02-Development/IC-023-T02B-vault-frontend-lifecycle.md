# IC-023-T02B — Vault frontend lifecycle

**Status:** IMPLEMENTED AND DEVELOPER-VERIFIED IN ISOLATED WORKTREE

**Authorized baseline:** `3319d9072afccb4f353e32e72cfed2a6a8223137`

**Branch:** `feature/ic-023-vault-frontend-lifecycle`

**Governance:** TTDM v2.1; Product Owner execution authority for IC-023-T02B only

## Scope

This checkpoint implements the owner-facing Personal Credential Vault lifecycle UI at `/vault`. It preserves the accepted IC-021 encrypted CRUD, IC-022 sensitive-authorization, and IC-023-T02A deleted-lifecycle contracts. It does not add or change backend behavior and does not implement purge, rotation, backup/recovery, maintenance, infrastructure, or deployment.

The responsive page provides active/deleted tabs, active type and label-prefix filters, opaque cursor previous/next navigation, create/edit/delete/reveal/restore actions, restore eligibility display, and explicit initial, list-loading, empty, retryable-error, and operation-status states. Dialogs are labeled, keyboard-operable, focus-restoring, and use the shared UI controls.

## Confirmed API contracts

- `GET /api/v1/vault/credentials?limit=<1..100>&cursor=<opaque>&type=<type>&prefix=<prefix>` returns `{ credentials, nextCursor }` with nonsecret metadata.
- `GET /api/v1/vault/deleted-credentials?limit=<1..100>&cursor=<opaque>` returns nonsecret metadata plus `restorationEligible` and `restorationExpiresAt`.
- `POST /api/v1/vault/reauthenticate` accepts `{ password }`, is CSRF protected, bound by the backend to the exact authenticated session, and returns `{ grant, expiresAt }`.
- Create accepts `{ credentialType, label, serviceLabel, origin, secretFields }` and returns `{ credential }` with HTTP 201.
- Patch accepts `{ expectedRevision, metadata, secretFields? }`; an omitted `secretFields` preserves current encrypted values.
- Reveal returns `{ credential: { id, revealed } }` with no-store response controls.
- Delete accepts `{ expectedRevision }` and returns an empty HTTP 204 response; the client explicitly decodes 204 as `null`.
- Restore accepts `{ expectedRevision }` and returns `{ credential }`.
- Every sensitive operation sends `X-CSRFToken` and `X-Vault-Grant`. Unlike ordinary CSRF-protected requests, it is attempted exactly once and is never replayed after `csrf_failed`, network failure, or another error.

## Security invariants

- Passwords, grants, and revealed fields remain only in component/function memory. No vault value is written to local storage, session storage, URLs, analytics, or logs.
- The reauthentication form has a synchronous submission latch and the manager has a second in-flight latch, preventing duplicate password submissions before React state propagation.
- Cancellation, route navigation, document hiding, `pagehide`, and unmount increment the sensitive-operation generation and clear pending grants, password UI, reveal state, display mode, timers, and tracked clipboard values.
- Generation checks occur after reauthentication and after the protected operation, so stale completions cannot reopen cleared dialogs or restore plaintext. List requests use an independent generation so stale filter/tab/page responses cannot overwrite current state.
- A grant is handed to one action closure once. The client does not retry grant-protected operations, including CSRF failures.
- Revealed values start masked and clear after 30 seconds, close, navigation, visibility loss, or unmount. Clipboard cleanup is best effort and only overwrites the clipboard when its current value still equals the copied secret.
- Create/edit secret inputs disappear when the editor is closed after success or cancellation. Post-commit refreshes return metadata only; plaintext is never reconstructed from mutation responses.
- Restore controls are disabled when server-provided `restorationEligible` is false. Client time is presentation-only and is not used to override eligibility.

## Implementation and tests

Frontend implementation:

- `apps/web/lib/api.ts` — typed vault contracts, list functions, CSRF-aware reauthentication, and non-replaying sensitive request path.
- `apps/web/app/vault/page.tsx` — vault route.
- `apps/web/components/vault-manager.tsx` — lifecycle UI, editor, reauthentication, reveal/copy handling, pagination, async invalidation, and accessible states.
- `apps/web/components/ui/button.tsx` — supplies the already-used ghost close-control variant through the shared primitive.

Focused coverage:

- `apps/web/lib/vault-api.test.ts` checks filter/cursor encoding, browser session credentials, exact create payload and headers, HTTP 204 delete decoding, and no replay after CSRF failure.
- `apps/web/components/vault-manager.test.tsx` checks filtering/pagination, deleted restore eligibility, duplicate reauthentication prevention, visibility cancellation while authorization is in flight, reveal clearing, create lifecycle/secret-editor teardown, and consumed-grant deletion failure without retry.

## Verification evidence

Environment: Windows sandbox, Node/npm versions constrained by the repository root package metadata.

- `npm run typecheck`: passed with no TypeScript errors.
- `npm run lint`: passed with zero warnings and zero errors.
- `npm test -- --run lib/vault-api.test.ts components/vault-manager.test.tsx`: 10/10 passed across 2 files.
- `npm test`: 60/60 passed across 11 files.
- `npm run build`: passed; Next.js compiled, typechecked, generated all 10 static pages, and included `/vault`.

An earlier expanded focused/full test run exposed one ambiguous test query because both the retained editor and overlaid reauthentication dialog intentionally contain a field labeled “Password.” The test was scoped to the last (reauthentication) field and both focused and complete suites then passed. This was a test-selector failure, not a product failure.

The production build emitted a non-failing Next.js workspace-root warning because both the preserved untracked root lockfile and `apps/web/package-lock.json` exist. No lockfile was removed or changed.

The root `package-lock.json` was inspected. It is an untracked minimal root-workspace lockfile containing package metadata and engine constraints only. It was preserved unchanged and is not part of T02B implementation.

## Limitations and residual risks

- Clipboard clearing depends on secure-context Clipboard API read/write permissions and is explicitly best effort; operating systems and clipboard managers may retain history outside application control.
- JavaScript strings cannot be deterministically zeroized. The implementation minimizes lifetime and references but cannot prove physical memory erasure.
- Browser automation in this checkpoint uses jsdom component tests; a real-browser accessibility and clipboard-permission qualification remains appropriate for IC-023-T02D.
- The frontend trusts the backend’s exact-session grant binding, one-use consumption, owner scoping, revision checks, encryption, retention predicate, and no-store headers as accepted contracts.
- Implementation verification was completed before Git finalization; finalization is governed by the separate IC-023-T02B-GIT-01 Product Owner authorization. PR merge remains separately controlled.

## Deferred and excluded work

Vault purge, key rotation, backup/recovery, maintenance operations, AWS, Redis, deployment, and backend behavior remain outside T02B authority. Final feature-wide browser/security evidence and consolidated acceptance remain deferred to IC-023-T02D.
