# F-02 — Identity & Administration

**Status:** Security remediation implementation complete; SOL exact-head review pending

**Feature branch:** `feature/identity-administration`

**Verified feature head:** `98b294fb4a8d17d7d5b30c54d8ed86a9f9d93702`

**Verified main baseline:** `5a5c56e819cb11ebc203c1fc57b7a0a229a74b32`

**Product Owner G0 authorization:** 2026-10-27

**Closeout verification date:** 2026-10-28

**SOL reviewer:** SOL

This record reconciles the integrated feature and newly executed closeout evidence. It does not authorize a feature-to-`main` merge. Task integration is complete; SOL closeout review and separate Product Owner exact-head merge authorization remain required.

## F02-SEC-001 activation-token remediation (2026-10-29)

The original F02-D01/D03 browser-URL limitation is remediated on `fix/f02-sec-001-activation-token-exposure`: activation delivery now uses `/activate#token=...`, the static client scrubs the fragment before form rendering, the dynamic token route is removed, and legacy path requests receive a constant non-reflecting 404 response. Existing invitation rows receive durable `LEGACY_PATH` provenance while new rows are `FRAGMENT_V1`.

A dry-run-by-default management command provides separately authorized, actor-attributed legacy revocation/reissue. It uses the lifecycle guard and row locks, revalidates eligibility, revokes expired records without replacement, and has native-MySQL concurrency, idempotence, rollback, and artifact-failure evidence. No non-test execution was performed.

Updated acceptance evidence is in `docs/tasks/F02-SEC-001/test-results.md`: 122 backend tests, 32 frontend tests, native migration/drift checks, TypeScript/lint/build, development/production synthetic-token scans, explicit legacy rejection, and a passing real-Chrome invitation-to-activation journey. This remediation does not authorize task integration, feature-to-main merge, IC-024, or a production command execution.

G2 locking remediation adds the shared lifecycle guard to ordinary invitation creation/reissue before target-user access. Native MySQL now exercises an ordinary re-invitation racing legacy remediation for the same pending user and proves one usable invitation, safe revocation, consistent audit attribution, and attributable retained delivery artifacts. The authoritative post-remediation full-suite count is 123 backend tests; frontend remains 32 tests with typecheck, lint, and build passing.

## Scope and gate history

F-02 contains IC-008 audit and authorization infrastructure, IC-006 invitation and activation, and IC-007 App Admin lifecycle administration. The Product Owner first approved F-02 and F02-D01 through F02-D08 as a planning baseline, then separately authorized each task through TTDM. Original decisions remain preserved in the task living documents.

| Task | Integrated scope | PR | Final reviewed head | Feature merge | Disposition |
| --- | --- | --- | --- | --- | --- |
| IC-008 | Audit model/service, vocabulary, authorization matrices | #13 | `734f7ed9a8046c2eb62e8bf298f2ea07c8b0f530` | `726edee0312a6ad5522c1bf1aa08936477386336` | SOL G2 pass; G3 integration authorized and completed |
| IC-006 | Invitation, activation, re-invitation, development delivery | #14 | `698f334420c1292688cb5b6cc68bd5a17950c11a` | `33db61b5cfb1e99d4dcff7719bd3a788cf572b43` | SOL exact-head G2 pass; integration authorized and completed |
| IC-007 | Administration, lifecycle, session revocation, deletion review | #15 | `28d3773dbc2bcaff384546f9aadc1a7f1fcb617d` | `98b294fb4a8d17d7d5b30c54d8ed86a9f9d93702` | SOL G2 pass; integrated at the verified feature head |

IC-024 permanent deletion remains deferred and depends on IC-007 and IC-023 vault safeguards. F-02 excludes permanent deletion, vault cleanup, self-registration, hosted delivery/deployment, audit viewing/retention, new roles, and new authentication methods.

## Consolidated acceptance matrix

Evidence marked closeout was run from the verified feature head on 2026-10-28. Named tests are implementation references and are newly executed only when included in the commands below.

| Decision | Integrated behavior | Task criteria and tests | Controls | Closeout and limitation |
| --- | --- | --- | --- | --- |
| F02-D01 — secure activation tokens | `accounts.invitations` creates 24-hour tokens, stores only digests, locks activation rows, and atomically revokes old tokens on re-invitation. Activation is single-use, gives generic invalid responses, and creates no session. | IC-006 AC-03/05/06/08/09; `InvitationServiceTests`, `InvitationApiTests`, `NativeConcurrentActivationTests`. | Raw tokens are limited to the development artifact/client request; replay, expiry, revocation, and malformed values are externally indistinguishable. | Backend suites and native MySQL concurrency passed. Database and filesystem commits require tested compensating cleanup. |
| F02-D02 — password policy | Activation applies a 12-character minimum and configured Django validators before token consumption. | IC-006 AC-07; password-policy and non-consumption tests. | Passwords are not returned or audited; errors are bounded. | Backend suites passed; policy remains configuration-dependent. |
| F02-D03 — safe development delivery | Explicit DEBUG-only file sink uses exclusive creation and cleanup on partial delivery or database failure. Tokens are absent from API responses and application logs. | IC-006 AC-04/10; collision, partial-write, commit-failure, and audit-failure tests. | Path containment, collision preservation, restrictive local mode where supported. | Backend suites passed. Windows ACL strength and URL exposure in browser/server/access logs remain environment responsibilities. |
| F02-D04 — App Admin separation | Active authenticated `is_app_admin=True` is required for invitation and user administration. Staff, superuser, and IT roles do not independently grant application administration. | IC-006 AC-01/02/11; IC-007 AC-01/02/03/09/10; policy, authorization, lifecycle, and CSRF tests. | Server-side default deny, bounded serialization, cookie sessions, and CSRF. | Backend/frontend suites passed; full browser journey not run. |
| F02-D05 — session revocation | Deactivation discovers and deletes all database sessions for the account inside the lifecycle transaction. Decode/delete failures fail closed; reactivation creates no session. | IC-007 AC-05/06/10/11; multi-session, malformed data, decode/delete, rollback, and audit-failure tests. | Session keys/decoded contents are not logged or audited; failure rolls back lifecycle and session changes. | Backend suites passed. Scan cost is O(total sessions); in-flight requests cannot be recalled. |
| F02-D06 — last-admin safeguard | `AdminLifecycleGuard` is a shared `select_for_update` serialization point with consistent lock ordering for reactivation, deactivation, and App Admin downgrade. | IC-007 AC-04/06/11; `LastAdminConcurrencyTests`. | Transactional shared lock preserves one active, activated App Admin. | Native MySQL suites passed. Future membership mutations must use the guard. |
| F02-D07 — security audit | `security_audit` stores immutable nonsecret actor snapshots and allowlisted action/target/outcome values. Critical mutation/audit commits are atomic; denied recording is bounded best effort outside caller transactions. | IC-008 AC-01–09; IC-006 AC-10; IC-007 AC-08/11; audit migration/service/sanitization/failure-injection and integration tests. | Rejects secret-shaped/free-text identifiers; excludes email, IP, payloads, cookies, sessions, passwords, and tokens. | Security/full suites passed. Audit viewing, retention/purge, and controls against privileged direct database writes are out of scope. |
| F02-D08 — review, not deletion | The deletion-review route creates `AccountDeletionReview`; UI states that no deletion occurs. | IC-007 AC-07/09/12; non-destructive lifecycle and frontend tests. | No deletion, deactivation, cascade, ownership change, or cleanup. | Backend/frontend suites passed. IC-024 remains deferred pending IC-023 and separate authorization. |

## Newly executed closeout verification

Environment: Windows/PowerShell, repository `.venv`, Django test configuration with native MySQL, and repository Node/npm. Secrets and private account data are omitted.

| Command and directory | Result |
| --- | --- |
| `..\..\.venv\Scripts\python.exe manage.py test -v 1` (`apps/api`) | PASS — 112 tests in 248.979s |
| `..\..\.venv\Scripts\python.exe manage.py test security_audit accounts.tests.test_invitations accounts.tests.test_lifecycle -v 1` (`apps/api`) | PASS — 57 tests in 228.966s, including native MySQL invitation and App Admin concurrency |
| `..\..\.venv\Scripts\python.exe manage.py check --database default` (`apps/api`) | PASS — no issues |
| `..\..\.venv\Scripts\python.exe manage.py showmigrations accounts security_audit sessions` (`apps/api`) | PASS — accounts through `0003`, security audit through `0003`, sessions `0001` applied |
| `..\..\.venv\Scripts\python.exe manage.py migrate --check` (`apps/api`) | PASS (exit 0) |
| `..\..\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run` (`apps/api`) | PASS — no changes detected |
| `npm run typecheck` (`apps/web`) | PASS |
| `npm run lint` (`apps/web`) | PASS |
| `npm test -- --run` (`apps/web`, first combined run) | FAIL — 26/27; `AdminUsers` timed out awaiting its mocked asynchronous first page while the host was under concurrent load |
| `npm test -- --run` (`apps/web`, unchanged isolated rerun) | PASS — 27/27 across 6 files in 12.59s; no code change |
| `npm run build` (`apps/web`) | PASS — production build completed |
| `npx playwright test e2e/auth.spec.ts --reporter=line` (`apps/web`) | BLOCKED before scenario — local Playwright Chromium executable absent |
| `npm run validate` (repository root) | PASS — 19 required paths and basic `.env.example` secret-pattern check |
| `git diff --check` (repository root) | PASS — no whitespace errors |

The frontend timeout/rerun is retained rather than reported as an unqualified first-pass success.

## Integrated scenario disposition

The real-browser ten-step scenario was not executed because Playwright had no local Chromium binary; no browser evidence is claimed. Supported integration evidence covers:

1. invitation creation and pending inactive state through invitation API/service tests;
2. single-use activation and fresh-login behavior through invitation and frontend activation tests;
3. authorized listing, pagination, and role administration through lifecycle API and `AdminUsers` tests;
4. deactivation, cross-device denial, and fresh login after reactivation through lifecycle tests;
5. last-active-App-Admin protection through native MySQL concurrency tests;
6. non-destructive deletion review through lifecycle and frontend tests; and
7. negative authorization, CSRF, sanitization, and atomic audit behavior through matrices and security/integration tests.

The end-to-end visual/browser interaction remains explicitly unverified.

## Recovery checkpoint

The exact recoverable baseline is fetched ref `refs/remotes/origin/feature/identity-administration` at commit `98b294fb4a8d17d7d5b30c54d8ed86a9f9d93702`, tree `3efaeea1b893f99417fa6169cfad73465f7ab6bd`. The verified main baseline is its ancestor.

Verification procedure:

```text
git fetch origin main feature/identity-administration
git rev-parse origin/feature/identity-administration
git cat-file -t 98b294fb4a8d17d7d5b30c54d8ed86a9f9d93702
git rev-parse 98b294fb4a8d17d7d5b30c54d8ed86a9f9d93702^{tree}
git merge-base --is-ancestor 5a5c56e819cb11ebc203c1fc57b7a0a229a74b32 98b294fb4a8d17d7d5b30c54d8ed86a9f9d93702
```

No tag or independent remote backup ref was created because it was not authorized. A mutable remote-tracking branch is not an independent persistent recovery ref. If TTDM-WA-001 requires `backup/<feature>/<id>` or equivalent, its separately authorized creation and verification is an open release blocker. Recovery remains possible while the commit is reachable from GitHub or another clone.

## Residual risks and blockers

| ID | Risk or blocker | Disposition |
| --- | --- | --- |
| R-01 | Database/filesystem invitation delivery is not one atomic commit. | Compensating cleanup is tested; host/process failure between boundaries may require operator cleanup. |
| R-02 | Activation token exists in a URL/client flow. | History replacement and generic responses reduce exposure; browser history before replacement, reverse proxies, access logs, and mailbox access need control. |
| R-03 | Mailbox confidentiality depends on host ACLs. | Development-only gate and restrictive mode exist; Windows ACL guarantees are environment-dependent. |
| R-04 | Revocation scans all database sessions. | Correctness is tested; cost grows with session-table size. |
| R-05 | Already executing requests cannot be recalled. | Subsequent protected requests are denied. |
| R-06 | Audit viewing, retention/purge, and privileged direct-database controls are absent. | Outside F-02; future authorization/operations policy required. |
| R-07 | No hosted/CI environment was verified. | Evidence is local native MySQL/backend/frontend only. |
| R-08 | Real-browser journey is unverified. | Browser binary absent; API/service/component evidence is documented without fabrication. |
| R-09 | One frontend test timed out under concurrent load, then passed unchanged. | Retained as a potential timing/flakiness signal. |
| B-01 | No independent persistent recovery ref exists. | Separate PO authorization required if TTDM-WA-001 makes it a release prerequisite. |
| B-02 | Feature-to-`main` merge is unauthorized. | SOL exact-head review and separate PO authorization required. |
| B-03 | Permanent deletion is not accepted in F-02. | IC-024 remains deferred pending IC-023 and separate authorization. |

## Closeout status

The integrated feature satisfies the approved F02-D01 through F02-D08 scope in the newly executed backend, native MySQL, frontend, migration, and build checks, subject to the recorded browser, recovery, and operational limitations. No substantive code defect was changed during closeout.

**Feature Completed:** No. Ready for SOL exact-head closeout review only. The documentation PR targets `feature/identity-administration`; neither it nor the feature branch may be merged without separate Product Owner authorization.
