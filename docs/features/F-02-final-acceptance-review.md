# F-02 — Identity & Administration Final Acceptance Review

**Date:** 2026-10-29
**Method:** TTDM-WA-001
**Scope:** IC-006, IC-007, IC-008, and F02-SEC-001
**Verified feature branch:** `feature/identity-administration`
**Exact verified feature SHA:** `524c162290e4db0da954996fe2938dbbf27ca65a`
**Status:** Evidence complete; SOL independent closeout review and Product Owner final acceptance pending

This document is a documentation-only evidence package. It does not mark F-02 accepted, authorize a feature-to-`main` merge, authorize non-test legacy-invitation remediation, or authorize F-03.

## Integrated task and PR inventory

| Contract | Scope | PR | SOL-reviewed source | Feature integration |
| --- | --- | --- | --- | --- |
| IC-008 | Immutable controlled audit records, fail-closed critical audit writes, authorization matrices | #13 | `734f7ed9a8046c2eb62e8bf298f2ea07c8b0f530` | `726edee0312a6ad5522c1bf1aa08936477386336` |
| IC-006 | Admin invitation, digest-only activation tokens, password activation, safe development delivery | #14 | `698f334420c1292688cb5b6cc68bd5a17950c11a` | `33db61b5cfb1e99d4dcff7719bd3a788cf572b43` |
| IC-007 | App Admin user administration, lifecycle, session revocation, last-admin guard, deletion review | #15 | `28d3773dbc2bcaff384546f9aadc1a7f1fcb617d` | `98b294fb4a8d17d7d5b30c54d8ed86a9f9d93702` |
| F02-SEC-001 | Fragment-token activation, legacy-route rejection, provenance, controlled remediation | #18 | `ef9a58be5a318620c934a146ad66e493801b8b28` | `524c162290e4db0da954996fe2938dbbf27ca65a` |

PR #17 supplied the earlier feature closeout documentation at `c5aca48438b7aaca3b67c3fbb4753c432d7631ae`; PR #18 was integrated on that exact baseline. The final merge has parents `c5aca48438b7aaca3b67c3fbb4753c432d7631ae` and `ef9a58be5a318620c934a146ad66e493801b8b28`. The merge tree was verified equal to the approved remediation source tree.

## Newly executed closeout evidence

These commands were executed from exact feature SHA `524c162290e4db0da954996fe2938dbbf27ca65a` on 2026-10-29. They are distinct from historical evidence in the task documents.

Environment: Windows 11, PowerShell, repository `.venv`, Django 5.2.7, native Windows MySQL, Next.js 16.4.3, and installed Google Chrome. Browser work used a disposable SQLite database and test-only mailbox; both were removed afterward.

| Command or check | Result |
| --- | --- |
| `python manage.py check --database default` | PASS — no issues |
| `python manage.py migrate --check` | PASS — native MySQL current |
| `python manage.py makemigrations --check --dry-run` | PASS — no model drift |
| `python manage.py showmigrations accounts security_audit sessions` | PASS — accounts/security-audit through `0004`, sessions `0001` |
| `python manage.py test -v 1` | PASS — 123 tests in 313.963s on native MySQL |
| focused `security_audit`, invitation/API/remediation, lifecycle, and policy suites | PASS — 81 tests in 246.279s on native MySQL |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS — zero warnings |
| `npm test -- --run` | PASS — 7 files / 32 tests in 42.43s |
| `npm run build` | PASS — static `/activate`, no dynamic token route, Proxy present |
| Playwright real-Chrome invitation/activation/legacy rejection, first run | FAIL — 5s URL assertion expired while Django was still processing activation; server later recorded a broken pipe when the browser closed |
| Same Playwright scenario, unchanged rerun | PASS — 1/1 in 13.9s |
| Real-Chrome local/session storage and fragment inspection | PASS — token absent from both storage mechanisms; fragment scrubbed |
| Development log inspection | PASS — activation traffic logged only token-free `/activate`; API logs contained no token |
| Production SSR synthetic-token scan | PASS — token absent from `/activate` HTML |
| Production legacy-path scan | PASS — fixed non-reflecting 404; token absent from response |
| Production Next.js output inspection | PASS — tested requests emitted no token/request output |

The first browser timeout is retained as evidence rather than rewritten as an unqualified first-pass success. The backend showed no application error response; it was still processing password activation when Playwright closed the page. The unchanged warm rerun passed. This is a timing/flakiness signal, not a reproduced functional defect.

## Acceptance traceability matrix

| Acceptance area | Integrated behavior | Executable evidence | Result |
| --- | --- | --- | --- |
| Invitation authority | Only active authenticated App Admins can invite; IT role, staff, and superuser flags do not independently grant authority | invitation API authorization/CSRF matrix; policy and focused security suites | PASS |
| Invitation creation and reissue | Canonical pending account, grant updates, old invitation revocation, 24-hour TTL, exclusive file delivery | `InvitationServiceTests`, `InvitationApiTests`, artifact collision/failure tests | PASS |
| Activation secrecy | Random token, digest-only persistence, fragment delivery, immediate scrub, no SSR/log/storage/audit token | model/service tests, bootstrap tests, Chrome storage check, SSR/log scans | PASS |
| Activation validity | CSRF, password policy, expiry, revocation, replay denial, single use, generic errors, no automatic session | invitation/API/frontend tests and real-Chrome journey | PASS |
| Legacy exposure remediation | Dynamic route absent; legacy path gives constant non-reflecting 404; provenance migration marks old/new formats | production build/SSR scan, migration tests, Playwright rejection | PASS |
| Controlled legacy lifecycle | Dry-run default, explicit actor/execute, guard-first locking, lock-time revalidation, expired revoke/no reissue, idempotence | remediation command/service tests and native MySQL race tests | PASS |
| App Admin lifecycle | Bounded user list, role/admin edits, deactivate/reactivate, fresh login, non-destructive deletion review | lifecycle API/service/frontend tests | PASS |
| Session revocation | All database sessions for deactivated user removed; decode/delete failures roll back | lifecycle session and failure-injection tests | PASS |
| Last-admin safeguard | Shared singleton guard serializes activation, reactivation, downgrade, deactivation, invitation replacement, and remediation | native MySQL lifecycle and F02-SEC-001 concurrency tests | PASS |
| Audit attribution/integrity | Allowlisted immutable actor/target/outcome records; critical state and audit commit atomically; secrets rejected | IC-008 service/migration tests plus invitation/lifecycle rollback tests | PASS |
| Authorization and CSRF | Authentication, active-state, App Admin, role, ownership, and unsafe-request CSRF boundaries fail closed | authorization matrix, session, invitation, and lifecycle API suites | PASS |
| Scope boundary | Deletion review does not delete/deactivate/cascade; IC-024 remains deferred | lifecycle tests and repository diff inspection | PASS |

## Security and authorization matrix

| Subject or condition | Expected boundary | Closeout result |
| --- | --- | --- |
| Anonymous invitation/admin request | 401 | PASS |
| Inactive App Admin | 401 | PASS |
| IT member/editor/document admin without App Admin | 403 | PASS |
| Staff/superuser without application grant | no implicit App Admin authority | PASS |
| Missing/invalid CSRF on mutation | 403 generic CSRF error | PASS |
| Expired/revoked/replayed/malformed activation token | same bounded invalid-activation response | PASS |
| Last active activated App Admin removal | transactionally rejected | PASS |
| Concurrent admin-membership mutations | serialized through shared guard | PASS |
| Audit persistence failure | critical mutation rolled back | PASS |
| Delivery or database commit failure | state rolled back; created artifact compensated | PASS |
| Legacy/ordinary invitation race | one usable invitation; superseded artifacts unusable and attributable | PASS |
| Deactivated account with old session/cookie | subsequent protected access denied | PASS |

## Residual risks, limitations, and deferred work

1. Development file delivery and the database are separate resources. Tested compensation covers application-visible write/commit failures, but abrupt process or host loss can require artifact reconciliation.
2. Mailbox confidentiality depends on host ACLs; Windows mode semantics do not provide the same portable guarantee as POSIX `0600`.
3. Fragments avoid HTTP/server transmission, SSR serialization, and normal request logs, but browser extensions and same-page scripts remain within the browser trust boundary. Upstream infrastructure must still avoid sensitive URL telemetry.
4. Superseded file-sink artifacts are retained as email-like delivery evidence. Their tokens are revoked and tested unusable.
5. Database-session revocation scans the session table because Django sessions do not index user ID. Cost is O(total sessions), and already executing requests cannot be recalled.
6. Audit viewing/export, retention/purge, and controls against privileged direct database mutation remain outside F-02. No retention period is approved.
7. The real-browser scenario had one closeout timing timeout followed by an unchanged passing rerun. Hosted/CI browser performance is not verified.
8. No hosted deployment or external mail provider was tested; evidence is local native MySQL and local Chrome.
9. No independent recovery ref was created for final SHA `524c162…`; the merged GitHub feature ref and PR history currently retain it. Any additional release checkpoint requires separate authorization.
10. IC-024 permanent deletion remains deferred pending IC-023 and separate Product Owner authorization. ADR-001 and IC-024 paths were unchanged relative to the F-02 main baseline.
11. The legacy-invitation remediation command was tested only with test data and was not executed against non-test data. Operational execution requires separate approval and runbook controls.

## Recommendation and gate

**Recommendation: READY for SOL independent F-02 closeout review.** All approved F-02 implementation contracts and the security remediation are integrated at the exact baseline, and fresh native-MySQL, frontend, browser, migration, authorization, audit, concurrency, rollback, idempotence, and token-exposure evidence passes. The initial browser timing failure and residual operational limitations are explicitly retained for SOL assessment.

This recommendation is not final acceptance. SOL must independently review this exact evidence and SHA. The Product Owner must make the final F-02 acceptance and any feature-to-`main` decision separately. No feature-to-main merge is authorized by this package.
