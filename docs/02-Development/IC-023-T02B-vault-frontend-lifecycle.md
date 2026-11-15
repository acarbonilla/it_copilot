# IC-023-T02B — Vault frontend lifecycle

**Status:** R01 ACCEPTED; PUBLICATION AUTHORIZED; MERGE HOLD PENDING PUBLISHED REVIEW

**Authorized baseline:** `3319d9072afccb4f353e32e72cfed2a6a8223137`

**Branch:** `feature/ic-023-vault-frontend-lifecycle`

**Governance:** TTDM v2.1; Product Owner execution authority for IC-023-T02B only

**R01 risk:** L3 — security-critical

**Initial acceptance and publication:** The Product Owner accepted the initial T02B implementation. Original commit `5fd753166365f06ff43c2a7f9a927dfbe86bde57` was published as [PR #31](https://github.com/acarbonilla/it_copilot/pull/31). R01 is corrective work within T02B and does not create a new development checkpoint.

**R01 acceptance:** Product Owner ACCEPTED IC-023-T02B-R01 based on reported verification evidence on November 15, 2026. This decision is separate from the original T02B acceptance. Selective publication of the three R01 paths to PR #31 is authorized; merge, review-thread resolution, and review-thread comments remain unauthorized.

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

## R01 review findings and remediation

The four PR #31 review findings were confirmed against the original commit and corrected within the frontend boundary:

1. **R01-01 — Editor secret lifetime.** The common sensitive-state cleanup now unmounts the credential editor as well as clearing reveal and grant state. Visibility loss, `pagehide`, sensitive-flow cancellation, route navigation, and component unmount therefore discard editor-owned secret fields. Reopening the editor creates fresh empty state. Regression coverage exercises visibility loss, `pagehide`, direct cancellation, and unmount.
2. **R01-02 — Credential type metadata.** Editor state clears `origin` whenever the selected type is not `LOGIN`, and clears `service_label` unless the type is `LOGIN` or `API_TOKEN`. Submission also constructs a type-specific metadata object, providing a second fail-closed boundary: LOGIN submits service label/origin, API token submits service label only, and SSH/generic submit neither. Regression coverage verifies all three transitions from LOGIN against the backend allowlists.
3. **R01-03 — Pagination race.** A synchronous pagination-transition latch prevents multiple state transitions before React renders the loading state. Previous/Next are disabled while loading and still honor cursor/history availability. The latch clears only for the current list generation, preserving stale-response rejection. Regression coverage fires three immediate Next clicks and verifies one cursor request and a stable page counter.
4. **R01-04 — Session initialization error.** Session initialization now has distinct loading, ready, and error states. Non-authentication failures render an actionable error without credential metadata and provide a retry. HTTP 401 retains the existing login redirect behavior. List loading begins only after successful session validation. Regression coverage verifies HTTP 503 failure, metadata suppression, retry, and recovery.

The original one-use grant, no protected-operation replay, generation-based stale completion rejection, no browser storage, and no secret logging behavior remains unchanged and covered by the focused API/component tests.

## Verification evidence

Environment: Windows sandbox, Node/npm versions constrained by the repository root package metadata.

- `npm run typecheck`: passed with no TypeScript errors.
- `npm run lint`: passed with zero warnings and zero errors.
- `npm test -- --run lib/vault-api.test.ts components/vault-manager.test.tsx`: 19/19 passed across 2 files.
- `npm test`: 69/69 passed across 11 files.
- `npm run build`: passed; Next.js compiled, typechecked, generated all 10 static pages, and included `/vault`.
- `git diff --check`: passed with line-ending conversion warnings only and no whitespace errors.

### R01 evidence provenance

- **CURRENT:** Focused vault regression suite after R01: 19/19 passed across 2 files.
- **CURRENT:** Authoritative full Vitest rerun executed alone: 69/69 passed across 11 files.
- **CURRENT:** TypeScript passed with no errors; ESLint passed with zero warnings/errors.
- **CURRENT:** Production build passed, including static generation of `/vault`; the known non-failing multiple-lockfile workspace-root warning remains.
- **CURRENT:** Final `git diff --check` passed, with line-ending conversion warnings only.
- **CURRENT:** Backend diff is empty.
- **CURRENT NEGATIVE PATH:** A prior full-suite run executed concurrently with the production build timed out one existing create-flow test at Vitest's 5-second limit (68 passed, 1 timed out). The focused suite had passed, and the authoritative full-suite rerun without concurrent build load passed 69/69. This is recorded as resource-contention/flaky timing evidence, not represented as a passing run.
- **REUSED:** Backend API and metadata allowlists were inspected from the accepted backend implementation; no backend behavior changed.
- **STALE:** The initial T02B totals (focused 10/10 and full 60/60) describe original commit `5fd7531` and are not R01 completion evidence.
- **MISSING:** Real-browser accessibility, lifecycle, and clipboard-permission evidence remains outside this local jsdom verification and is recommended for consolidated IC-023-T02D review.

An earlier expanded focused/full test run exposed one ambiguous test query because both the retained editor and overlaid reauthentication dialog intentionally contain a field labeled “Password.” The test was scoped to the last (reauthentication) field and both focused and complete suites then passed. This was a test-selector failure, not a product failure.

The production build emitted a non-failing Next.js workspace-root warning because both the preserved untracked root lockfile and `apps/web/package-lock.json` exist. No lockfile was removed or changed.

The root `package-lock.json` was inspected. It is an untracked minimal root-workspace lockfile containing package metadata and engine constraints only. It was preserved unchanged and is not part of T02B implementation.

## Limitations and residual risks

- Clipboard clearing depends on secure-context Clipboard API read/write permissions and is explicitly best effort; operating systems and clipboard managers may retain history outside application control.
- JavaScript strings cannot be deterministically zeroized. The implementation minimizes lifetime and references but cannot prove physical memory erasure.
- Browser automation in this checkpoint uses jsdom component tests; a real-browser accessibility and clipboard-permission qualification remains appropriate for IC-023-T02D.
- The frontend trusts the backend’s exact-session grant binding, one-use consumption, owner scoping, revision checks, encryption, retention predicate, and no-store headers as accepted contracts.
- Product Owner authorization IC-023-T02B-R01-GIT-01 permits only the documentation update, selective commit of the three accepted R01 paths, and non-force push to existing PR #31. Merge and review-thread resolution or comments remain unauthorized.
- R01 publication advances PR #31 from original head `5fd7531`; the PR must remain open and unmerged until the published remediation and review-thread state are verified and separate Product Owner merge authorization is issued.
- Consolidated independent review in IC-023-T02D remains recommended. No Product Owner decision on that recommendation has been supplied or inferred.

## Current repository and merge status

R01 corrective work targets `feature/ic-023-vault-frontend-lifecycle` and existing PR #31. The known root `package-lock.json` remains untracked, untouched, and excluded from publication. Product Owner authorization permits publication of only the three accepted R01 paths. **Merge HOLD:** PR #31 must remain open and unmerged pending verification of the published commit and review threads plus separate Product Owner merge authorization.

## Deferred and excluded work

Vault purge, key rotation, backup/recovery, maintenance operations, AWS, Redis, deployment, and backend behavior remain outside T02B authority. Final feature-wide browser/security evidence and consolidated acceptance remain deferred to IC-023-T02D.
