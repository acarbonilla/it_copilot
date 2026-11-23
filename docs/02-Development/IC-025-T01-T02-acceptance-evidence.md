# IC-025 T01/T02 — Consolidated MVP Acceptance Evidence

**Task:** IC-025-T01-T02-01
**Feature:** F-06 — MVP Acceptance
**Risk:** L3 — security-sensitive verification
**Execution date:** 2026-11-23 (Asia/Singapore)
**Execution status:** **HOLD — evidence consolidation complete; targeted integrated acceptance not safely executable on the available checkout**

## 1. Revision, worktree, and environment

This cycle did not identify an existing T01/T02 report. Evidence was reconciled without changing application source, migrations, schema, operational data, provider state, or Git history.

| Item | Observed value |
| --- | --- |
| Active worktree | `C:\Users\dc\PycharmProjects\it_copilot` |
| Active branch / HEAD | `feature/documentation-management` / `7bbb4c663a7daebe659e700dd0240556f6cc86ff` |
| Tracking ref | `origin/feature/documentation-management` |
| Working-tree state before report | Dirty: 7 tracked modifications and 12 untracked top-level status entries, including partial F-04 code/migration/docs and the F-05/F-06 records |
| Historical integrated main baseline | `bcd6df267d87596de4ba6616080f31d4d42913eb` (`origin/main`, PR #34 merge) |
| Relationship | `bcd6df2…` is **not** an ancestor of active HEAD; active HEAD predates and diverges from the accepted integrated main baseline |
| Host | Windows 10 build 19045, PowerShell |
| Runtime | Python 3.13.5; Django 5.2.7; Node.js v24.13.0; npm 10.8.2 |
| Browsers detected | Google Chrome 157.0.8103.79; Microsoft Edge 157.0.4341.46 |
| Native MySQL | CLI not available on `PATH`; no connection or credential was attempted |
| Provider | No activation or network request performed |

The exact active revision was inspected but **not represented as an integrated tested revision**. It cannot support an F-01–F-05 acceptance run because it is dirty, divergent from `origin/main`, and contains only partial uncommitted later-feature material. Historical results below retain their own exact revisions. No test result is attributed to `7bbb4c…` or `bcd6df2…` unless its source record explicitly did so.

## 2. Acceptance matrix

| Criterion | Classification | Evidence and precise gap |
| --- | --- | --- |
| AC-01 — F-01–F-05 status | **PASS WITH LIMITATIONS** | F-01 technical acceptance was recommended but its recorded PO gate remained pending; F-02 evidence was complete but SOL/PO closeout remained pending; F-03 was SOL-accepted `PASS WITH ACCEPTED LIMITATIONS`; F-04 post-merge verification was complete but pending SOL closure; F-05 received PO `PASS WITH ACCEPTED LIMITATIONS`. All feature merge chains are present in historical `origin/main`, but the decision states are not uniformly final. |
| AC-02 — Authenticated frontend/API/MySQL workflows | **NOT VERIFIED** | Feature-specific browser/API/MySQL evidence exists, but no provenance-backed authenticated F-01–F-05 workflow was executed on one clean integrated revision. The active checkout is unsuitable and native MySQL was unavailable to this process. |
| AC-03 — Roles, isolation, sessions | **PASS WITH LIMITATIONS** | F-01/F-02 native-MySQL and browser evidence covers login/logout, CSRF, deactivation, cookie replay, roles, last-admin guards, and session revocation. F-03/F-04/F-05 records cover owner/cross-owner denials. F-05 retains the missing consolidated cross-component isolation matrix and real-browser gaps. |
| AC-04 — Documents and Copilot retrieval | **PASS WITH LIMITATIONS** | F-03 accepted processing/integrity evidence and F-04 accepted task/post-merge evidence support authorized retrieval, references-only/insufficient outcomes, citation metadata, and provider-disabled behavior. F-04 lacked a post-merge native-MySQL rerun and authenticated real-browser Copilot run. |
| AC-05 — Vault workflows | **PASS WITH LIMITATIONS** | F-05 PO acceptance and checkpoint records support CRUD, grants, reauthentication, reveal, lifecycle, delete/restore, and fail-closed foundations. Full authenticated real-browser workflow evidence is incomplete; operational purge, key maintenance, backup, and recovery remain prohibited or held. |
| AC-06 — Secret hygiene | **NOT VERIFIED** | Historical token, response, error, audit, and selected browser-storage checks passed. F-05 explicitly records no consolidated sentinel scan across API/log/audit/browser/build/repository surfaces and no complete real-browser storage/cache/console assurance. Missing critical evidence is not a pass. |
| AC-07 — Disabled/restricted capabilities | **PASS WITH LIMITATIONS** | F-04 verified that provider/private transfer gates were disabled and no transport was installed. F-05 records fail-closed operational foundations and explicit prohibitions. Positive operational purge/recovery/rotation was correctly not run; a single integrated route/capability denial matrix remains absent. |
| AC-08 — MySQL, migrations, regression, security | **PASS WITH LIMITATIONS** | Accepted records contain native-MySQL migration/concurrency/regression results for F-01–F-05 and post-merge frontend/backend checks. F-04 post-merge MySQL was unavailable, and this cycle could not perform a clean-baseline drift/regression rerun. Evidence is reconciled, not freshly reproduced. |
| AC-09 — Defect disposition | **PASS** | Section 7 consolidates blockers, limitations, ownership, disposition, and acceptance impact. No new runtime Critical/High defect was observed because no integrated runtime test was claimed; the missing critical evidence is a blocking verification gap. |
| AC-10 — Consolidated report | **PASS** | This report provides the required provenance, matrix, reused/new evidence, gaps, findings, retained holds, and T03 recommendation. It does not perform T03 or declare final MVP acceptance. |

Overall T01/T02 disposition: **HOLD**. The report is ready for SOL review, but final T03 acceptance is not ready on the current evidence.

## 3. Reused evidence and provenance

| Feature / source | Exact provenance and reusable result | Continuing applicability / limitation |
| --- | --- | --- |
| F-01 — `docs/features/F-01-acceptance-review.md` | IC-002–IC-005 task heads and PR merges; native MySQL/security evidence; 45 integrated backend tests; 17 frontend tests; one real two-tab Edge E2E. Technical acceptance recommended. | Runtime foundations remain relevant, but the recorded PO feature gate was pending and no current integrated rerun exists. |
| F-02 — `docs/features/F-02-final-acceptance-review.md` | Exact feature SHA `524c162290e4db0da954996fe2938dbbf27ca65a`; 123 native-MySQL tests, 81 focused tests, 32 frontend tests, build/type/lint, Chrome activation/storage/log scans. | Strong auth/session/role evidence; closeout document still states SOL/PO decision pending. Initial Chrome timing failure followed by unchanged pass is retained. |
| F-03 — `docs/features/F-03-acceptance-review.md` and `docs/02-Development/IC-029A-F03-feature-finalization.md` | Acceptance head `ae48121003322bc61c5e539fd5eb73b739fd201f`; SOL `PASS WITH ACCEPTED LIMITATIONS`; 120-test document suite (12 skipped), 12 native concurrency tests, frontend unit/type/lint. | Browser/build evidence was reused from earlier batches; local Windows/NTFS/native-MySQL boundary and recovery/purge limitations remain. |
| F-04 — `docs/02-Development/IC-018…`, `IC-019…`, `IC-020…`, and `F-04-post-merge-verification-and-closure.md` | PR #23 `aa9048d…`, #24 `cac14f1…`, #25 `a0f1cfa…`; post-merge 50 frontend and 46 backend tests, build/type/lint; historical IC-018 24 and IC-019 16 native-MySQL tests. Provider disabled. | Post-merge native MySQL failed before assertions due unavailable credentials; no Copilot browser E2E/accessibility audit; closure remained pending SOL. |
| F-05 — `docs/features/F-05-final-acceptance-review.md` and IC-021/022/023 checkpoint records | PO `PASS WITH ACCEPTED LIMITATIONS`; accepted merged main `bcd6df267d87596de4ba6616080f31d4d42913eb`, PR #34. Final rotation record: 63 focused run/61 passed/2 skipped; provider subset 32/31/1; full vault 115/101/14; FIX-01 9 SQLite plus 1 native MySQL passed. | Explicitly not full G1 compliance. Browser, consolidated hygiene/isolation, native interleavings, recovery, and operational restrictions remain. |

The historical `origin/main` chain at `bcd6df2…` includes F-04 merges followed by F-05 G1 and IC-021–IC-023 merges. Evidence was not treated as proof of the dirty active tree.

## 4. Newly executed checks

Only non-destructive checks necessary to establish provenance and availability were run:

- Confirmed active HEAD, branch, tracking ref, dirty status, and all registered worktrees.
- Confirmed `origin/main` at `bcd6df2…` and that it is not an ancestor of active HEAD.
- Inspected F-04 worktrees at `49c043d…`, `80d2553…`, and `e4d165e…`; each was clean.
- Inspected F-05 checkpoint worktrees and exact heads. The IC-023 frontend worktree alone had an untracked `package-lock.json`; no file was changed or removed.
- Confirmed installed runtimes and Chrome/Edge versions.
- Confirmed native `mysql` CLI was unavailable on `PATH`.
- Inspected the authoritative requirements, execution plan, feature acceptance records, task evidence, and the historical integrated-main documents.

No application test suite was rerun. Running it against the active dirty/divergent checkout would not close the integrated-MVP gap and could misstate provenance.

## 5. Unavailable or unexecuted verification

- Clean exact-`bcd6df2…` integrated frontend/API/native-MySQL execution.
- One authenticated browser journey covering login/logout/deactivation, documents, Copilot, and Vault on the same baseline.
- Chrome and Edge integrated runs with disposable identities and data.
- Cross-owner/cross-role denial matrix spanning documents, Copilot citations, and Vault.
- F-04 post-merge native-MySQL rerun and real-browser Copilot workflow.
- Full Vault real-browser CRUD/reauthentication/reveal/delete/restore workflow.
- Consolidated secret sentinel scanning across responses, errors, logs, audit rows, browser storage/cache/console, build output, fixtures, and repository surfaces.
- Integrated denial proof for every disabled/held operational route.
- Any positive operational purge, rotation, retirement, destruction, backup, or recovery action; these were prohibited, not merely unavailable.

## 6. Security and integration findings

1. **No authoritative clean execution target in the active worktree.** The checkout cannot be used to claim integrated MVP acceptance. This is an evidence/baseline blocker, not a discovered application runtime defect.
2. **Historical main is integrated but not freshly executable here.** `bcd6df2…` contains the merge chain, while native MySQL access and a clean checked-out worktree were not available under the task's no-Git-change boundary.
3. **Security evidence is strong but fragmented.** Authorization, session, retrieval, and Vault controls have feature-level coverage; the ratified consolidated cross-component and secret-hygiene proofs remain missing.
4. **Provider remained disabled.** No credential, network request, configuration change, or private-document transfer occurred.
5. **No prohibited operational action occurred.** No source/schema/migration edit, operational database change, Git staging/publication, purge, account deletion, key operation, backup/recovery, AWS, Redis, or deployment was performed.

## 7. Defect and acceptance-gap register

| ID | Criterion | Severity / type | Finding | Owner | Disposition and acceptance impact |
| --- | --- | --- | --- | --- | --- |
| G-01 | AC-02, AC-08 | Blocking evidence gap | No clean exact integrated baseline was available for targeted execution; active HEAD is dirty and divergent. | Product Owner / release owner | Provide or authorize a clean worktree at the selected integrated SHA and approved disposable environment. **Blocks final MVP acceptance.** |
| G-02 | AC-02, AC-04, AC-05 | Blocking evidence gap | No single authenticated real-browser F-01–F-05 journey exists; F-04 and full Vault browser workflows remain incomplete. | F-06 verification owner | Run the bounded Chrome/Edge matrix on the authorized clean baseline. **Blocks unqualified PASS.** |
| G-03 | AC-06 | Blocking security-evidence gap | Consolidated secret-hygiene sentinel coverage is explicitly absent. | Security/SOL | Execute a non-sensitive sentinel matrix across required surfaces. **AC-06 remains NOT VERIFIED.** |
| G-04 | AC-03, AC-07 | Medium evidence limitation | Consolidated cross-component owner/role and disabled-operation denial matrices are absent. | Security/SOL | Target exact negative paths; preserve generic failures and no secret output. Candidate accepted limitation only if explicitly dispositioned. |
| G-05 | AC-01 | Governance limitation | F-01, F-02, and F-04 records do not show the same final decision maturity as F-03/F-05. | SOL / Product Owner | Reconcile or explicitly disposition the recorded pending gates in T03. |
| L-F04-01 | AC-04, AC-08 | Accepted limitation | F-04 post-merge native MySQL and browser/accessibility evidence unavailable; eight moderate npm audit findings recorded. | F-04 owner | Retain; no automatic dependency remediation authorized. |

No new Critical or High enabled-functionality defect was observed. That statement is not a pass claim: runtime coverage was deliberately not fabricated from an unsuitable checkout.

## 8. Retained F-05 limitations and holds

All F-05 limitations remain unchanged:

- **L01:** interrupted rotation reconciliation is not implemented.
- **L02:** rotation versus CRUD/lifecycle/backup/purge native interleavings are incomplete.
- **L03:** operational key custody, ACL/SID configuration, activation, and escrow are deferred.
- **P2-01:** snapshot size enforcement while subprocess output streams is incomplete.
- **P2-02:** signed-manifest expiry, invalidation generation, and verification policy need complete enforcement.
- **D01:** MySQL Shell backup fallback is incomplete.
- **D02:** full crash reconciliation is incomplete.
- **D03:** operational custody, SID setup, and escrow are pending.
- **D04:** positive operational destructive-purge verification is incomplete.
- **D05:** consolidated independent security review is pending.

Operational KEK/DEK rotation, retirement, activation, destruction, backup/recovery, and destructive purge remain prohibited or on mandatory HOLD. IC-024 account deletion remains deferred and unauthorized. Original F-05 real-browser, secret-hygiene, cross-component isolation, restart/recovery, and complete-G1 evidence gaps are retained.

## 9. Remaining verification needed before T03

1. Select and authorize one clean integrated revision (historically `bcd6df2…`, or a later explicitly reconciled SHA) and record a clean status.
2. Make approved native MySQL test access available without exposing credentials; confirm migration state and run only the targeted integrated seams.
3. Execute the bounded authenticated Chrome/Edge journeys and negative owner/role/session cases using disposable records.
4. Execute the consolidated non-secret sentinel hygiene matrix.
5. Reconcile F-01/F-02/F-04 pending governance wording with explicit SOL/PO dispositions.
6. Update this report with exact commands, totals, skips, artifacts, cleanup, and any defects. Do not exercise prohibited operational paths.

## 10. Recommendation for IC-025-T03

**Recommendation: NOT READY — HOLD T03 final MVP acceptance.** T01 evidence consolidation is complete and suitable for SOL review. T02 cannot be considered complete because the missing integrated browser/native-MySQL/security evidence is material and the available active checkout is not an authoritative clean F-01–F-05 baseline.

The next action should be a separately controlled targeted verification pass on a clean authorized integrated SHA, limited to G-01 through G-04. T03 must remain a separate Product Owner decision and must not infer final acceptance from the historical feature passes.

## 11. Publication status

This task created only this local Markdown evidence report. No Git add, commit, push, merge, PR, reset, rebase, or branch deletion was performed. The repository remains dirty and unpublished.

---

## 12. IC-025-T02-GAP-01 checkpoint — 2026-11-23

**Authorization:** focused verification of GAP-01 through GAP-03 only. Earlier findings above remain part of the record.
**Checkpoint outcome:** **GAP-01 PASS; GAP-02 HOLD; GAP-03 PARTIAL.**
**T03 disposition:** **NOT READY — HOLD.**

### 12.1 Exact integrated revision and checkout provenance

Read-only remote inspection returned `bcd6df267d87596de4ba6616080f31d4d42913eb` for `refs/heads/main` at `https://github.com/acarbonilla/it_copilot.git`, matching the historical integrated main baseline. The commit is PR #34's merge of the final accepted F-05 checkpoint and follows the accepted F-01 through F-04 merge chain.

No existing worktree was both clean and at this SHA. An isolated detached verification checkout was therefore created at:

`C:\Users\dc\PycharmProjects\it_copilot\.tmp\ic025-gap01-bcd6df2`

The checkout contained `accounts`, `session_auth`, `security_audit`, `documents`, `copilot`, `vault`, and the Next.js web application. Final status was `## HEAD (no branch)` with no modified or untracked entries. Existing worktrees were not reset, cleaned, rebased, overwritten, or deleted.

Environment observed for this checkpoint:

- Windows 10 build 19045; Python 3.13.5; Django 5.2.7.
- Node.js v24.13.0; npm 10.8.2.
- Chrome 157.0.8103.79 and Edge 157.0.4341.46 installed.
- Native MySQL service `MySQL80` running; server version 8.0.37.
- The exact committed dependency `cryptography==46.0.3` was missing from the shared project virtual environment and was installed at that pinned version solely to load the verified baseline. No application dependency file or source file changed.

**GAP-01 result: PASS.** The remote-verified integrated SHA was safely accessed in a clean isolated checkout. Checkout creation alone is not treated as functional MVP verification.

### 12.2 GAP-02 targeted integration outcome

The following readiness checks were executed against the isolated SHA:

| Check | Result |
| --- | --- |
| `git ls-remote origin refs/heads/main` | PASS — returned exact SHA `bcd6df2…` |
| Detached checkout module and status inspection | PASS — expected F-01–F-05 modules present; clean status |
| `manage.py check --database default` with protected local environment values loaded without printing them | PASS — no issues |
| Native MySQL connection/version | PASS — MySQL 8.0.37 reachable |
| `manage.py migrate --check` | Exit 1 — configured database is behind the integrated baseline; no migration was applied |
| Database boundary inspection | Configured database is not named as a test database; one unrelated/unauthorized `test_oms` schema exists with 17 tables |
| Chromium workflow | **NOT EXECUTED** |

The configured database was rejected for acceptance mutations because it is non-test and behind the baseline's migration state. The only existing `test_` schema could not be established as an authorized IT Support Copilot disposable database. Creating a suitable schema would require migrations, which this authorization expressly prohibited. The installed browsers were therefore available, but there was no safe database on which to create disposable users, documents, Copilot records, and Vault records.

No unit, component, or SQLite result was substituted for the required real Chromium/native-MySQL sequence. Login/navigation, document upload-to-READY, reference-only Copilot retrieval, cross-owner denial, Vault create/reauthenticate/reveal/update/delete/restore, and logout/replay denial remain unexecuted as one consolidated workflow.

**GAP-02 result: HOLD.** Native MySQL connectivity is verified, but the required representative integration sequence is **NOT VERIFIED** because no authorized current disposable database existed and creating/migrating one was prohibited.

### 12.3 GAP-03 secret-hygiene outcome

No canary was submitted because doing so would require the unavailable safe mutable environment. Targeted executable/source inspection on the exact integrated SHA produced the following sanitized evidence:

| Check | Result |
| --- | --- |
| Provider configuration and adapter invocation | PASS — both enablement gates are false; adapter raised `ProviderUnavailable`; no transport is installed |
| Public operational rotation entry points | PASS — KEK and DEK entry points each raised `OperationalRotationDisabled` before any operation |
| HTTP route inspection | PASS — no purge, rotation, backup, recovery, retirement, or destruction HTTP route exists |
| Copilot/document dependency AST inspection | PASS — no `vault` import from Copilot or documents; no direct Vault-content retrieval path found |
| Vault response inspection | PASS with runtime limitation — create/update/list/detail/delete/restore return metadata only; reveal returns plaintext only after active-session and single-use-grant enforcement and sets `Cache-Control: no-store, private`, `Pragma: no-cache`, and `X-Content-Type-Options: nosniff` |
| Browser handling inspection | PASS with runtime limitation — secrets/grants are held in component memory, not local/session storage; revealed values clear after 30 seconds, page hide, visibility loss, error, navigation, or unmount; clipboard clearing is attempted if unchanged |
| Audit-model inspection | PASS with runtime limitation — allowlisted action/target/outcome identifiers provide no payload or secret field |
| Cross-owner Vault denial, browser storage/cache/console scan, API/log/audit canary scan | **NOT VERIFIED at runtime** |

Existing accepted F-02/F-05 evidence for token/storage/log handling, owner-only Vault authorization, generic errors, no-store responses, grant binding, and secret-safe audits remains reused with its original limitations. Static/executable boundary checks do not replace a canary-based runtime scan.

**GAP-03 result: PARTIAL.** No newly observed plaintext disclosure or provider/Vault coupling was found, and fail-closed provider/rotation boundaries executed successfully. Cross-owner runtime denial and sanitized canary scans across API, logs, audits, browser storage/cache/console, and persisted chat remain **NOT VERIFIED**.

### 12.4 F06 acceptance impact

| Criterion | Checkpoint impact |
| --- | --- |
| AC-01 | Unchanged: `PASS WITH LIMITATIONS`; feature decision maturity remains as reconciled above. |
| AC-02 | Remains `NOT VERIFIED`; clean baseline is now available, but the consolidated Chromium/API/MySQL workflow could not run. |
| AC-03 | Remains `PASS WITH LIMITATIONS`; cross-owner integrated runtime denial was not rerun. |
| AC-04 | Remains `PASS WITH LIMITATIONS`; provider-disabled and dependency boundaries gained exact-SHA evidence, but browser retrieval was not run. |
| AC-05 | Remains `PASS WITH LIMITATIONS`; Vault code and fail-closed boundaries were confirmed, but the browser lifecycle was not run. |
| AC-06 | Improves from `NOT VERIFIED` to **`PASS WITH LIMITATIONS` only for static/executable boundary evidence**; the required runtime canary surfaces remain not verified, so this does not support unqualified acceptance. |
| AC-07 | Remains `PASS WITH LIMITATIONS`; provider and public rotation guards passed, routes are absent, and all operational holds remain. |
| AC-08 | Remains `PASS WITH LIMITATIONS`; exact-SHA MySQL connectivity is new evidence, but the non-test schema is behind and no integrated regression was permitted. |
| AC-09 | Remains `PASS`; no new runtime defect was observed, and the environmental/governance blocker is recorded below. |
| AC-10 | Remains `PASS`; this checkpoint supplements the consolidated package without performing T03. |

### 12.5 New findings and remaining evidence

| ID | Type / severity | Finding | Disposition |
| --- | --- | --- | --- |
| G-01 | Resolved evidence gap | Clean remote-verified integrated baseline is now available at `bcd6df2…`. | Closed for checkout provenance only. |
| G-02A | Blocking environment/governance gap | No authorized, current, disposable IT Support Copilot MySQL schema exists. The configured non-test schema has pending migrations; schema creation/migration was prohibited. | **HOLD GAP-02.** PO/SOL must provide a pre-provisioned current disposable database or separately authorize creation/migration of an isolated test schema. |
| G-02B | Blocking evidence gap | Required real-Chromium integrated workflow remains unexecuted because it depends on G-02A. | **NOT VERIFIED.** Do not substitute unit tests. |
| G-03A | Security-evidence limitation | No runtime canary response/log/audit/storage/cache/console/persisted-chat scan or cross-owner Vault attempt was possible. | **PARTIAL.** Execute only after G-02A is resolved. |

No Critical or High enabled-MVP defect was newly observed. That is not a functional pass claim because the representative runtime sequence did not execute.

### 12.6 Preserved limitations, holds, and T03 recommendation

Every F-05 L01–L03, P2-01/P2-02, D01–D05 limitation and original evidence gap in Section 8 remains in force. Operational KEK/DEK rotation, key retirement/activation/destruction, backup/recovery, destructive purge, and IC-024 account deletion remain prohibited or on mandatory HOLD. No AWS, Redis, deployment, provider activation, provider request, or private-data transfer occurred.

**T03 recommendation: NOT READY — HOLD.** GAP-01 is closed, but GAP-02 is blocked and GAP-03 is only partial. A narrow continuation should occur only after an authorized, already-current disposable MySQL schema and disposable identities/fixtures are supplied, or after separate authorization permits isolated test-schema provisioning. Then execute the prescribed Chromium workflow and sanitized canary inspection on the same exact integrated SHA.

### 12.7 Change and publication status

The integrated verification checkout remained clean. Outside that checkout, the exact pinned Python package was installed into the existing project virtual environment and this Markdown checkpoint was appended. No application source, migration, schema, operational data, provider configuration, existing worktree, or Git history was changed. No Git staging, commit, push, PR, merge, reset, rebase, worktree deletion, or publication occurred.

---

## 13. IC-025-T02-GAP-02 runtime checkpoint — 2026-11-23

**Authorization:** one isolated disposable MySQL/Chromium runtime sequence and runtime secret-hygiene verification.
**Baseline:** `bcd6df267d87596de4ba6616080f31d4d42913eb`, detached clean checkout established by Section 12.
**Checkpoint outcome:** **Migrations PASS; Chromium integration HOLD; secret hygiene HOLD.**
**Blocking finding:** **one High defect in enabled MVP behavior.**

### 13.1 Disposable environment and migration target

The existing configured database was not used for fixtures or mutations. Before creation, the environment was verified as local native MySQL at `127.0.0.1:3306`, server version 8.0.37. The existing configured database was `my_database`; it remained untouched by this checkpoint.

The uniquely named acceptance database was:

`it_copilot_f06_acceptance_20261123_gap02a`

Safety evidence:

| Check | Result |
| --- | --- |
| Host locality | PASS — loopback `127.0.0.1`, native `MySQL80` service |
| Name validation | PASS — exact allowlisted lowercase/underscore identifier |
| Preexistence query | PASS — zero matching schemas before creation |
| Post-creation target check | PASS — `DATABASE()` matched the exact disposable identifier |
| Pre-migration contents | PASS — zero tables |
| Existing Django migrations | PASS — all committed migrations applied only to the disposable database |
| Post-migration check | PASS — `manage.py migrate --check` exit 0 |
| Resulting schema | 48 migration records; 39 tables |

No migration was generated, changed, or applied to `my_database`, `test_oms`, or another schema. The disposable database is intentionally retained as authorized.

### 13.2 Runtime components and targeted execution

Only the required local components were started: Django/DRF on port 8000, Next.js 16.4.3 on port 3000, native MySQL 8.0.37, the bounded one-shot document and retrieval-index workers, and installed headless Google Chrome 157.0.8103.79. All local web/API processes were stopped after the checkpoint.

The committed frontend lockfile was installed without upgrades (`488` packages; the previously recorded eight moderate npm findings remained). Next.js rewrote tracked generated `apps/web/next-env.d.ts` during development startup; that single generated change was restored to the exact committed content. Final integrated-checkout Git status was clean.

A temporary external harness used runtime-generated synthetic identities, document text, and Vault values. It was not added to application source. Execution results:

| Workflow step | Result |
| --- | --- |
| A — disposable identities | PASS — isolated active IT-member identities created |
| B — login and authenticated navigation | PASS — real Chrome login and protected navigation succeeded |
| C — document upload | PASS — harmless TXT uploaded through the frontend/API |
| D — processing and READY | PASS — one-shot processing completed and UI displayed `active · ready` |
| E — Copilot authorized references | PASS — retrieval index processed; real Chrome displayed references-only result and the authorized document label; provider remained disabled |
| F — cross-owner/ineligible denial | NOT VERIFIED in the final sequence; execution stopped before the second identity phase |
| G — Vault create | **FAIL/HOLD** — step-up reauthentication returned 201, but the subsequent browser request was blocked by CORS before reaching Django |
| H — Vault reveal/update/delete/restore | NOT VERIFIED because G failed |
| I — logout and replay denial | Historical evidence reused; final combined-sequence step not reached |

The disposable database retained sanitized evidence from the diagnostic runs: 10 synthetic users, 3 documents, 3 Copilot conversations, 6 Copilot messages, and **0 Vault records**. Repeated diagnostic runs used new synthetic values; they did not touch operational data.

### 13.3 High defect — Vault browser CORS contract

**ID:** F06-H01
**Severity:** **HIGH**
**Affected criterion:** AC-02, AC-05, AC-06
**Affected enabled workflow:** every browser Vault sensitive operation after successful step-up authorization.

Observed behavior:

1. The frontend successfully called `POST /api/v1/vault/reauthenticate`; Django returned `201` with a single-use grant.
2. The frontend then attempted the required sensitive request using `X-Vault-Grant` as specified by the ratified F-05 contract.
3. That request never reached the Vault credential endpoint.
4. A targeted Django CORS middleware preflight reproduced the cause:
   - preflight status: `200`;
   - exact frontend origin allowed;
   - allowed headers: `accept, authorization, content-type, user-agent, x-csrftoken, x-requested-with`;
   - `x-vault-grant` allowed: **false**.

The integrated baseline sets `CORS_ALLOWED_ORIGINS` and credentials but does not extend `CORS_ALLOW_HEADERS` with the ratified `X-Vault-Grant` header. Installed Chrome therefore blocks Vault create/reveal/update/delete/restore from the separate Next.js origin. Backend/unit evidence did not expose this browser integration failure.

**Disposition:** HOLD. No source change or automatic remediation was performed. This High defect affects enabled MVP functionality and must be separately authorized, fixed, reviewed, and reverified before T03.

### 13.4 Runtime secret-hygiene result

Provider state was confirmed false for both provider enablement and private-transfer authorization. The completed document/Copilot path returned references only. No Vault canary reached a credential endpoint, no Vault record was created, and no authorized reveal occurred because F06-H01 blocked the sensitive request.

Consequently:

- normal Vault list returned no credential data, but create/list/detail secrecy with a created canary was not demonstrated;
- reveal-without-grant and authorized no-store reveal were not reached in the final flow;
- browser local/session storage, log, audit, and persisted-chat canary scans could not establish end-to-end Vault hygiene;
- cross-owner Vault reads could not be tested because no Vault record existed;
- Copilot/Vault non-coupling and operational/provider restrictions retain the exact-SHA static/executable evidence from Section 12.

**Secret-hygiene result: HOLD / NOT VERIFIED for the required runtime canary sequence.** No unintended disclosure was observed, but missing evidence is not a pass. Expected authorized plaintext reveal was never reached and is not claimed.

### 13.5 AC-01 through AC-10 updated disposition

| Criterion | Updated disposition | GAP-02 effect |
| --- | --- | --- |
| AC-01 | PASS WITH LIMITATIONS | Unchanged feature-evidence reconciliation. |
| AC-02 | **HOLD** | Login/document/API/MySQL/Copilot integration passed, but enabled Vault browser integration failed with F06-H01. |
| AC-03 | PASS WITH LIMITATIONS | Historical role/owner/session evidence retained; cross-owner final-sequence denial was not reached. |
| AC-04 | PASS WITH LIMITATIONS | Exact-SHA Chrome/API/MySQL document-to-Copilot references-only flow passed; provider remained disabled. |
| AC-05 | **HOLD** | Browser Vault lifecycle is unusable across origins because the required grant header is rejected by CORS. |
| AC-06 | **HOLD / NOT VERIFIED** | Runtime Vault canary lifecycle and cross-surface scan could not execute past the CORS blocker. |
| AC-07 | PASS WITH LIMITATIONS | Provider remained disabled; Section 12's operational guard/route evidence remains applicable. |
| AC-08 | PASS WITH LIMITATIONS | Disposable native-MySQL creation, exact-target migrations, READY processing, and retrieval indexing passed; no broad regression rerun was authorized. |
| AC-09 | PASS | F06-H01 is recorded with severity, impact, evidence, ownership need, and blocking disposition. |
| AC-10 | PASS | This checkpoint updates the consolidated report without performing T03. |

### 13.6 Remaining gaps and T03 recommendation

Required before T03 can proceed:

1. Separately authorize and correct F06-H01 so the exact frontend origin may send only the required Vault grant header while preserving the narrow CORS boundary.
2. Independently review the fix and rerun the single bounded Chrome workflow from Vault create through restore, cross-owner denial, logout denial, and runtime canary scans.
3. Retain all F-05 L01–L03, P2-01/P2-02, D01–D05 limitations and mandatory operational holds; do not exercise operational rotation, retirement, destruction, backup/recovery, purge, provider transfer, or IC-024.

**F06 acceptance status: HOLD.**
**T03 recommendation: NOT READY — do not proceed until F06-H01 is remediated and the blocked GAP-02/GAP-03 runtime evidence passes.**

### 13.7 Change and publication status

No application source, migration, permanent environment configuration, operational database, real-user data, provider state, infrastructure, or Git history was changed. The isolated integrated checkout ended clean. The disposable database and synthetic fixtures were retained as authorized. The external temporary harness and runtime directories remain under the primary workspace `.tmp` area. No Git staging, commit, push, PR, merge, reset, rebase, worktree deletion, or publication occurred.

---

## 14. IC-025-T02-FIX-01 corrective checkpoint — 2026-11-23

**Defect:** F06-H01 — `X-Vault-Grant` CORS rejection
**Baseline:** `bcd6df267d87596de4ba6616080f31d4d42913eb`
**Correction workspace:** `C:\Users\dc\PycharmProjects\it_copilot\.tmp\ic025-fix01-bcd6df2`
**Disposition:** **F06-H01 FIXED in the local correction candidate; focused and Chromium verification PASS.**

### 14.1 Baseline, database, and root-cause reconfirmation

A second detached correction worktree was created at the exact verified integrated SHA so the clean GAP-01/GAP-02 checkout remained preserved. Before correction:

- correction worktree status was clean at `bcd6df2…`;
- native MySQL target was exactly `it_copilot_f06_acceptance_20261123_gap02a` on local port 3306;
- the database retained 48 migration records and 39 tables;
- no migration was reapplied and no schema command was run;
- actual Django CORS preflight returned `200` for `http://localhost:3000` but did not include `x-vault-grant` in `Access-Control-Allow-Headers`.

The frontend uses the ratified `X-Vault-Grant` header for sensitive requests. Vault reauthentication returned a grant successfully, but Chrome blocked the following request at preflight. The root cause was therefore confirmed as the missing header in Django's CORS request-header allowlist; no alternate cause or unrelated correction was pursued.

### 14.2 Minimal correction and local diff

Only two files changed in the correction workspace:

1. `apps/api/config/settings/base.py`
   - imports `corsheaders.defaults.default_headers`;
   - sets `CORS_ALLOW_HEADERS = (*default_headers, "x-vault-grant")`.
2. `apps/api/vault/tests/test_api.py`
   - adds one focused preflight regression proving the required header is allowed for the exact approved frontend origin and that an unapproved origin receives no allow-origin header.

The existing default header allowlist, exact credentialed origin, cookies, CSRF, authentication, grant format/validation, and response contracts remain unchanged. No wildcard header/origin, CORS disablement, CSRF bypass, logging, response exposure, or unrelated module change was introduced.

### 14.3 Focused regression results

Final focused command executed six tests using the isolated SQLite test settings:

- new approved/unapproved-origin Vault CORS preflight test;
- existing sensitive-route CSRF and grant requirement test;
- all five sensitive operations consume one grant each;
- replay and malformed/oversized proof denial;
- expired, revoked, and wrong-session grant denial;
- cross-owner/admin/missing-target generic denial and grant consumption.

**Result:** `6` tests passed in `19.010s`; zero failures, zero skips; Django system check reported no issues.

An earlier invocation used an incorrect test class name and ended with one loader error after the two correctly selected tests passed. It performed no application operation; the exact intended six-test command was corrected and passed as recorded above.

Post-fix middleware verification:

| Check | Result |
| --- | --- |
| Approved origin preflight status | PASS — 200 |
| Existing `x-csrftoken` permission retained | PASS |
| `x-vault-grant` permitted | PASS |
| Unapproved origin allowed | PASS — false/no allow-origin header |
| Authentication, CSRF, invalid/replay/expired/wrong-session/cross-owner grant enforcement | PASS — focused regressions |

### 14.4 Targeted Chromium Vault workflow

Installed Google Chrome 157.0.8103.79 ran against the corrected Django API, unchanged Next.js frontend, local native MySQL 8.0.37, and the retained disposable database. Runtime-generated synthetic values were used and omitted from this report.

The previously blocked sequence actually executed:

| Operation | Result |
| --- | --- |
| Login and protected navigation | PASS |
| Vault create with dummy login fields | PASS |
| Password reauthentication / single-use step-up | PASS |
| Reveal without a grant | PASS — denied 403 |
| Authorized reveal | PASS — expected plaintext only in reveal response/UI; response included `no-store` |
| Update metadata and secret | PASS |
| Soft delete | PASS |
| Deleted-list visibility and restore | PASS |
| Cross-owner Vault detail | PASS — generic 404 denial |
| Logout and subsequent Vault/Copilot access | PASS — redirected/denied to login |

The retained disposable database ended with 12 synthetic users, 3 documents, 3 Copilot conversations, 6 Copilot messages, 1 restored Vault record, and 37 controlled audit events. No operational record or schema was used.

### 14.5 Runtime synthetic-canary hygiene

The external harness used unique per-run document and Vault canaries and asserted only sanitized outcomes. Results:

- normal Vault create/list/detail and unauthorized/cross-owner responses did not contain Vault plaintext;
- authorized reveal contained the expected plaintext and was excluded from the unintended-disclosure scan;
- reveal response was `Cache-Control: no-store, private`;
- browser `localStorage` and `sessionStorage` contained no Vault canary after the sensitive lifecycle;
- browser console and captured Django/Next.js logs contained no Vault canary;
- controlled audit identifiers contained no Vault canary;
- persisted Copilot messages contained no Vault canary;
- Copilot/document source boundaries remained independent of Vault content;
- provider enablement and private-transfer authorization remained false;
- no operational rotation, retirement, destruction, backup/recovery, purge, or account-deletion function was executed.

**Canary hygiene result: PASS for the authorized targeted runtime surfaces.** This is not a production-readiness or all-telemetry claim; the existing local-MVP boundary and retained F-05 limitations remain.

### 14.6 F06-AC-01 through AC-10 impact

| Criterion | Corrected disposition | FIX-01 effect |
| --- | --- | --- |
| AC-01 | PASS WITH LIMITATIONS | Feature evidence and decision limitations remain unchanged. |
| AC-02 | PASS WITH LIMITATIONS | Across GAP-02/FIX-01, login, frontend/API/native-MySQL document READY, Copilot references, Vault lifecycle, and logout denial executed successfully on the same disposable environment. |
| AC-03 | PASS WITH LIMITATIONS | Focused invalid/expired/replay/wrong-session/cross-owner grant tests and real-Chrome cross-owner Vault denial passed; historical cross-feature evidence remains applicable. |
| AC-04 | PASS WITH LIMITATIONS | Prior exact-baseline document-to-Copilot references-only runtime pass retained; provider remained disabled during FIX-01. |
| AC-05 | PASS WITH LIMITATIONS | Browser Vault create, step-up, reveal, update, soft delete, restore, and cross-owner denial passed after the minimal fix. Operational capabilities remain outside this pass. |
| AC-06 | PASS WITH LIMITATIONS | Targeted runtime canary checks passed across normal/reveal/denial responses, browser storage, logs, audits, and Copilot persistence. Broader production telemetry is outside the local-MVP boundary. |
| AC-07 | PASS WITH LIMITATIONS | Provider/private transfer remained disabled and all F-05 operational holds were preserved. |
| AC-08 | PASS WITH LIMITATIONS | Native MySQL disposable schema, migrations from GAP-02, READY/index workers, focused regressions, and corrected runtime integration are reconciled; no broad unchanged suite was rerun. |
| AC-09 | PASS | F06-H01 was confirmed, minimally corrected, tested, and closed in the local candidate; no new Critical/High defect was found. |
| AC-10 | PASS | Consolidated evidence is updated for SOL/T03 review without declaring final acceptance. |

### 14.7 Defect disposition, remaining limitations, and T03 readiness

**F06-H01 status: FIXED in the uncommitted local correction candidate.** The High blocker is no longer reproduced after the two-file diff. No new Critical or High defect was observed.

Remaining limitations are the previously accepted feature/local-environment boundaries, including all F-05 L01–L03, P2-01/P2-02, D01–D05 findings and mandatory operational holds; F-04's eight moderate dependency findings and accepted browser/native-history qualifications; and the fact that this correction is a local uncommitted diff because publication was prohibited. No operational Vault capability is accepted or enabled by this correction.

**T03 readiness recommendation: READY for SOL review and IC-025-T03 decision packaging, with accepted limitations retained.** T03 must bind the exact baseline plus the two-file FIX-01 diff (or a separately authorized integrated revision with an identical reviewed tree). This recommendation is not final MVP acceptance and does not authorize staging, commit, publication, merge, deployment, provider activation, or any operational Vault action.

### 14.8 Change and publication status

- Clean preserved baseline checkout: unchanged and clean at `bcd6df2…`.
- Correction checkout: detached at `bcd6df2…`, modified only in `apps/api/config/settings/base.py` and `apps/api/vault/tests/test_api.py`.
- Primary worktree: pre-existing unrelated changes preserved; this Markdown report appended.
- Local Django/Next.js processes: stopped.
- Disposable database and synthetic fixtures: retained as authorized.
- Git: no staging, commit, push, PR, merge, reset, rebase, worktree deletion, or publication performed.
