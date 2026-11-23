# F-06 — Final Local MVP Acceptance Review

**Task:** IC-025-T03-01
**Risk:** L3 — final acceptance review
**Review date:** 2026-11-23 (Asia/Singapore)
**Exact integrated main:** `af768f16a9dd242d135eda253901c7fb23ca582a`
**Acceptance boundary:** Local Windows MVP development environment only
**SOL recommendation:** **PASS WITH ACCEPTED LIMITATIONS**
**Product Owner decision:** **PASS WITH ACCEPTED LIMITATIONS — LOCAL MVP DEVELOPMENT ONLY**
**Acceptance date:** 2026-11-23
**Accepted revision:** `af768f16a9dd242d135eda253901c7fb23ca582a`

## 1. Executive acceptance summary

The Product Owner accepted F-06 and the integrated F-01 through F-05 implementation as **PASS WITH ACCEPTED LIMITATIONS — LOCAL MVP DEVELOPMENT ONLY** on 2026-11-23 at `af768f16a9dd242d135eda253901c7fb23ca582a`. F-06 consolidated the feature evidence, established a clean integrated baseline, exercised a bounded native-MySQL/Chromium workflow, verified targeted sensitive-data hygiene, identified the browser-blocking Vault CORS defect F06-H01, and verified its minimal correction after merge.

The local MVP demonstrates authenticated frontend/API/native-MySQL behavior for login, document upload and READY processing, authorized reference-only Copilot retrieval, Vault create/reauthenticate/reveal/update/delete/restore, cross-owner denial, logout denial, and the targeted secret-hygiene surfaces. The external AI provider and private-document transfer remained disabled.

No unresolved Critical or High defect affecting enabled local-MVP functionality remains in the reviewed evidence. The result is not full G1 compliance, production readiness, deployment approval, provider activation, or authorization for operational Vault maintenance. F-05 limitations and mandatory operational HOLDs remain binding.

## 2. Integrated baseline and provenance

Remote `main` was verified at `af768f16a9dd242d135eda253901c7fb23ca582a`. The commit is the merge of PR [#35](https://github.com/acarbonilla/it_copilot/pull/35) and has parents:

- prior integrated F-01–F-05 main: `bcd6df267d87596de4ba6616080f31d4d42913eb`;
- reviewed F06-H01 correction: `1e19268b379fefbdb5baa74d60c20585e8ffe675`.

The complete `bcd6df2… → af768f1…` advance changes exactly:

- `apps/api/config/settings/base.py`;
- `apps/api/vault/tests/test_api.py`.

No unrelated change entered `main`. The merged configuration preserves `corsheaders.defaults.default_headers` and adds only `x-vault-grant` to `CORS_ALLOW_HEADERS`. The merged focused regression proves the approved local frontend origin receives the required header while an unapproved origin remains denied.

## 3. Final F06 acceptance matrix

| Criterion | Final classification | Supporting evidence and retained limitation |
| --- | --- | --- |
| F06-AC-01 — Feature completion and integration | **PASS WITH LIMITATIONS** | Git/PR provenance reconciles F-01 through F-05 on integrated main and records each feature's accepted or recommended state. F-03 and F-05 retain accepted limitations; earlier F-01/F-02/F-04 records contain historical pending-gate wording that does not override their merged implementation evidence. This review does not silently upgrade feature-specific limits to full G1 compliance. |
| F06-AC-02 — Authenticated frontend/API/MySQL workflows | **PASS WITH LIMITATIONS** | On the disposable native-MySQL environment, real Chrome completed login/navigation, TXT upload, READY processing, Copilot reference display, Vault lifecycle, and logout/access denial across Django/DRF and Next.js. The evidence is local and targeted, not a hosted or production matrix. |
| F06-AC-03 — Roles, isolation, sessions | **PASS WITH LIMITATIONS** | Historical F-01/F-02 role, CSRF, deactivation, session-revocation, replay, and last-admin evidence was reconciled with F-03/F-04/F-05 owner checks. FIX-01 focused invalid/malformed/replay/expired/revoked/wrong-session grant tests passed, and real-Chrome cross-owner Vault detail returned generic 404. No production identity infrastructure was tested. |
| F06-AC-04 — Documents and Copilot retrieval | **PASS WITH LIMITATIONS** | Real Chrome uploaded a harmless TXT document; the bounded processor published READY; the retrieval worker indexed it; Copilot displayed the authorized document as a reference with no synthesized answer. Historical native race/integrity evidence remains applicable. Provider activation and private transfer remain prohibited; citations remain non-clickable and no post-merge browser accessibility audit was added. |
| F06-AC-05 — Vault lifecycle and fail-closed controls | **PASS WITH LIMITATIONS** | After F06-H01 correction, real Chrome passed create, password step-up, no-grant 403 denial, authorized no-store reveal, secret/metadata update, soft delete, deleted listing, restore, cross-owner denial, and logout denial. Operational purge, rotation, retirement, backup, and recovery are explicitly excluded and held. |
| F06-AC-06 — Sensitive-data hygiene | **PASS WITH LIMITATIONS** | Unique synthetic Vault canaries were absent from normal create/list/detail and unauthorized/cross-owner responses, browser local/session storage, browser console, captured local logs, audit identifiers, and persisted Copilot messages. Expected plaintext appeared only in the authorized reveal response/UI, which was `no-store`. This is targeted local evidence, not a claim about every production telemetry or extension surface. |
| F06-AC-07 — Disabled/restricted capabilities | **PASS WITH LIMITATIONS** | Provider and private-transfer flags remained false; no provider transport is installed. Exact-SHA inspection confirmed no operational Vault HTTP routes, public rotation functions fail closed, and Copilot/documents do not import Vault. Disabled operational capabilities retain HOLD rather than being reclassified as functionally passed. |
| F06-AC-08 — MySQL, migrations, regression, security | **PASS WITH LIMITATIONS** | A unique local database was proven absent, created on MySQL 8.0.37, verified as the exact target, and populated with 48 existing migration records/39 tables. Document/index workers and targeted Chromium/API integration passed. Publication-focused security regression passed 6/6; exact merged-main CORS regression passed 1/1. Historical native concurrency/regression evidence was reused; unchanged full suites were not rerun. |
| F06-AC-09 — Defects and limitations | **PASS** | F06-H01 was recorded High, blocked acceptance, received a minimal two-file correction, passed focused and runtime verification, and was merged through PR #35. Post-merge provenance and exact-SHA regression pass. No unresolved Critical/High enabled-functionality defect is known. The retained limitation/HOLD register remains explicit below. |
| F06-AC-10 — Final recommendation and PO package | **PASS** | This document provides the exact baseline, matrix, evidence, defect closure, restrictions, exclusions, SOL recommendation, and the Product Owner's final acceptance recorded on 2026-11-23. |

## 4. Reused and post-merge verification evidence

### Reused accepted evidence

- **F-01:** IC-002–IC-005 native-MySQL, authentication/session/CSRF/role, frontend, and real-Edge evidence recorded in `F-01-acceptance-review.md` and task records.
- **F-02:** exact feature SHA `524c162290e4db0da954996fe2938dbbf27ca65a`; 123 native-MySQL tests, 81 focused security tests, 32 frontend tests, production build, and Chrome activation/storage/log scans.
- **F-03:** SOL `PASS WITH ACCEPTED LIMITATIONS`; acceptance head `ae48121003322bc61c5e539fd5eb73b739fd201f`; 120 document tests with 12 skips, 12 native concurrency tests, frontend checks, and retained real-Chrome evidence.
- **F-04:** merged PRs #23–#25; post-merge 50 frontend and 46 backend tests; historical 24 IC-018 and 16 IC-019 native-MySQL tests; provider-disabled/reference-only evidence.
- **F-05:** Product Owner `PASS WITH ACCEPTED LIMITATIONS` at integrated main `bcd6df2…`; accepted IC-021/022/023 checkpoint suites and selected native concurrency/recovery foundations, subject to the retained restrictions below.
- **F-06 T01/T02:** complete provenance, gap, defect, environment, and runtime history in `docs/02-Development/IC-025-T01-T02-acceptance-evidence.md`.

### Newly established F-06 runtime evidence

- Remote-verified clean integrated baseline and isolated checkouts.
- Native MySQL 8.0.37 disposable database `it_copilot_f06_acceptance_20261123_gap02a`; exact-target migration verification; no operational database mutation.
- Real-Chrome document-to-READY-to-Copilot reference-only flow.
- Real-Chrome Vault create/step-up/reveal/update/delete/restore, cross-owner denial, and logout denial.
- Targeted runtime canary checks across response, storage, console/log, audit, and Copilot-persistence surfaces.
- F06-H01 focused final candidate regression: 6 tests passed, zero failures/skips.
- Exact merged-main post-merge check: `vault.tests.test_api.VaultCorsTests` passed 1/1 in 0.012s; Django system check reported no issues; detached checkout remained clean at `af768f1…`.

## 5. F06-H01 closure

| Item | Final record |
| --- | --- |
| Defect | Browser rejected the required `X-Vault-Grant` header during CORS preflight, blocking every sensitive Vault request after successful step-up. |
| Severity | High — enabled local-MVP workflow blocker. |
| Root cause | Django used the default CORS header allowlist, which omitted the ratified custom header. |
| Correction | Preserve `default_headers` and append only `x-vault-grant`; add focused approved/unapproved-origin regression. |
| Source | `1e19268b379fefbdb5baa74d60c20585e8ffe675` |
| PR / merge | PR #35; merged as `af768f16a9dd242d135eda253901c7fb23ca582a`. |
| Verification | Six focused security tests passed; Chrome Vault/cross-owner/logout/canary workflow passed; exact merged-main CORS test passed 1/1. |
| Final disposition | **CLOSED — FIXED, VERIFIED, AND MERGED.** |

## 6. Remaining limitations and unverified requirements

F-05 remains **PASS WITH ACCEPTED LIMITATIONS** for local MVP development. The following remain unchanged:

- **L01:** interrupted rotation reconciliation is not implemented.
- **L02:** rotation versus CRUD/lifecycle/backup/purge native interleavings are incomplete.
- **L03:** operational key custody, ACL/SID configuration, activation, and escrow are deferred.
- **P2-01:** snapshot size enforcement while subprocess output streams is incomplete.
- **P2-02:** signed-manifest expiry, invalidation generation, and verification policy require complete enforcement.
- **D01:** MySQL Shell backup fallback is incomplete.
- **D02:** full crash reconciliation is incomplete.
- **D03:** operational custody, SID setup, and escrow are pending.
- **D04:** positive operational destructive-purge verification is incomplete.
- **D05:** consolidated independent security review remains pending.

Original incomplete F-05 G1 evidence remains visible where not superseded by F-06's targeted local checks: full restart/recovery assurance, complete operational interleavings, complete cross-component dependency/security review, and every ratified criterion not directly supported by an accepted record. Disabled operational behavior is not converted to PASS merely because it was not invoked.

Other retained local-MVP limitations include Windows/NTFS and native-MySQL scope; no hosted deployment; no production browser/telemetry assurance; no malware certification; coordinated database/private-artifact backup requirement; report-only document purge/quarantine disposition; F-04 non-clickable citations, first-page conversation bound, MySQL FULLTEXT behavior, and local worker/scheduler dependencies; eight previously recorded moderate frontend dependency findings; and no full real-browser accessibility/assistive-technology audit.

## 7. Mandatory F-05 and provider restrictions

The following remain prohibited or on mandatory HOLD:

- operational KEK or DEK rotation;
- key activation, retirement, or destruction;
- operational backup or recovery;
- operational destructive purge;
- IC-024 permanent account deletion;
- external AI provider activation or credential use;
- private-document transfer to an external provider.

F-06 acceptance cannot override these controls. Any future authorization requires its own scoped requirements, security review, evidence, and Product Owner decision.

## 8. Explicit exclusions

This review does not accept or authorize:

- production readiness, deployment, hosting, AWS, Redis, Celery, or other infrastructure;
- provider-generated answers, private-data transfer, tools, autonomous agents, web search, attachments, or multimodal behavior;
- operational Vault key/backup/recovery/purge activities;
- account deletion under IC-024;
- broad dependency remediation or automatic upgrades;
- external mail, object storage, queue, vector, or search services;
- any feature or requirement not included in the ratified F-01 through F-06 local MVP boundary.

## 9. Local MVP acceptance boundary

The recommended decision applies only to the reviewed local Windows development configuration using Next.js, Django/DRF, native MySQL, private local document storage, installed Chromium, disabled provider/private transfer, and disposable test records. It recognizes the enabled local MVP workflows and fail-closed restrictions demonstrated by accepted evidence.

It does not represent certification, compliance approval, operational security approval, disaster-recovery qualification, production service-level assurance, or permission to relax any retained HOLD.

## 10. Final SOL recommendation

**Recommend: PASS WITH ACCEPTED LIMITATIONS for the bounded local MVP development environment.**

Rationale:

- F-01 through F-05 are integrated on the exact reviewed main revision.
- Material authenticated frontend/API/native-MySQL workflows were demonstrated in real Chromium.
- Roles, sessions, owner isolation, authorized retrieval, provider-disabled behavior, Vault sensitive workflows, and targeted canary hygiene have provenance-backed evidence.
- The sole F-06 High blocker, F06-H01, is fixed, verified, and merged with no unrelated main change.
- No unresolved Critical/High defect affecting enabled local-MVP behavior is known.
- Remaining limitations are explicit, bounded, and do not enable or validate prohibited operational capabilities.

The Product Owner subsequently accepted this recommendation for the exact revision and bounded local-development scope recorded below. The recommendation itself did not authorize any broader operational or production scope.

## 11. Product Owner decision

**Decision status:** **ACCEPTED**
**Disposition:** **PASS WITH ACCEPTED LIMITATIONS — LOCAL MVP DEVELOPMENT ONLY**
**Accepted revision:** `af768f16a9dd242d135eda253901c7fb23ca582a`
**Decision date:** 2026-11-23
**Accepted criteria:** F06-AC-01 through F06-AC-08 **PASS WITH LIMITATIONS**; F06-AC-09 and F06-AC-10 **PASS**.
**Accepted limitations / conditions:** All limitations in Section 6 and mandatory restrictions in Sections 7–9 remain binding. F06-H01 is **CLOSED — FIXED, VERIFIED, AND MERGED** through PR #35.
**Decision boundary:** This decision accepts the bounded local MVP development baseline only. It is not production-readiness, deployment, compliance, operational-security, provider-activation, private-data-transfer, or operational Vault authorization.
