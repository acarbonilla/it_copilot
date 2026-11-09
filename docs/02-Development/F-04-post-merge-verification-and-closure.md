# F-04 — Post-Merge Verification and Documentation Closure

**Status:** Verification complete; pending SOL closure review
**Verification branch:** `docs/f04-post-merge-closure`
**Verified `origin/main`:** `a0f1cfa1b4e0b0ffd46a4b653ff084f79cc5c7f6`
**Provider state:** Disabled; private-document transfer not authorized

## 1. Feature overview

F-04 delivers the local MVP Copilot flow over accepted F-01 through F-03 security boundaries. It indexes verified F-03 extracted text, reauthorizes bounded retrieval candidates at evidence-release time, persists owner-private conversations, returns either authorized references or insufficient evidence while synthesis is disabled, and exposes the workflow through an authenticated Next.js workspace.

The feature does not activate an external provider, transmit private documentation, add cloud infrastructure, or generate troubleshooting advice. The ratified requirements and D1–D14 decisions remain authoritative in `docs/features/F-04-consolidated-g1-proposal.md`.

## 2. Completed task register

| Task | Delivered capability | Closure state |
| --- | --- | --- |
| IC-031 | Ratified F-04 G1 requirements, D1–D14, and SOL clarifications | Historical requirements baseline |
| IC-018 | Authorized retrieval index and F-03 evidence-release boundary | Merged via PR #23 |
| IC-019 | Owner-private grounded conversations and disabled provider boundary | Merged via PR #24 |
| IC-020 | Responsive Copilot UI, integrated security, and stale-request corrections | Merged via PR #25 |

No new IC code was created for this post-merge verification activity.

## 3. PR and merge SHA register

| PR | Task | Accepted feature head | Merge SHA | Verified state |
| --- | --- | --- | --- | --- |
| #23 | IC-018 | `49c043d24a78cf69d1b27a5db5799cc3e680c333` | `aa9048dad5dcccba4fc5aae453b13e5b7c1f3554` | Merged; ancestor of verified `origin/main` |
| #24 | IC-019 | `80d25530a9e4f14fea863d5caa12148fb91dd59c` | `cac14f1246315f1e394b85ffa3635964ececbcbd` | Merged; ancestor of verified `origin/main` |
| #25 | IC-020 | `e4d165ed002a986fb64d57749ba20c03226c3376` | `a0f1cfa1b4e0b0ffd46a4b653ff084f79cc5c7f6` | Merged; verified `origin/main` HEAD |

Git ancestry was checked after a non-destructive `git fetch origin --prune` using `git merge-base --is-ancestor <merge-sha> origin/main` for all three merge commits. Each command returned success. GitHub metadata independently reported PRs #23, #24, and #25 as merged with the matching merge SHAs.

## 4. Implementation architecture

1. F-03 owns verified artifact access, current-version integrity, tombstone enforcement, authorization, and final evidence release.
2. IC-018 maintains a local MySQL FULLTEXT index through a transactional outbox and bounded database worker. Retrieval ranks at most 40 candidates and releases at most 8 chunks, 3 per document, and 12,000 tokens.
3. IC-019 serializes owner-private turns, reuses the guarded retrieval boundary, persists bounded conversation history, validates server citations, and applies rolling 30-day expiry.
4. With the provider disabled, relevant evidence produces reference metadata with empty assistant content; missing evidence produces an explicit insufficient result.
5. IC-020 consumes only versioned session-authenticated APIs. It renders metadata-only citations and protects asynchronous UI state with request generations, active-conversation identity, and unmount guards.

No browser component reads the database, filesystem, private chunks, storage keys, or provider credentials.

## 5. Verification environment

- Date: 2026-11-10, Asia/Singapore.
- Clean isolated worktree: `C:\Users\dc\PycharmProjects\it_copilot_f04closure`.
- Branch baseline: `docs/f04-post-merge-closure` from `origin/main` at `a0f1cfa1b4e0b0ffd46a4b653ff084f79cc5c7f6`.
- Node.js `v24.13.0`; npm `10.8.2`.
- Python `3.13.5`; Django `5.2.7`.
- Frontend dependencies installed from the committed lockfile with `npm install`; no audit fix or package upgrade was performed.
- SQLite test settings were used for portable Django verification.
- Native MySQL authentication was not available to this process.
- The original F-03 working tree, its untracked files, and `apps/web/next-env.d.ts` were preserved.

## 6. Exact verification commands and outcomes

### Frontend

Run from `apps/web`:

| Command | Outcome |
| --- | --- |
| `npm test` | 9 files passed; 50 tests passed; 0 failed; 0 skipped |
| `npm run typecheck` | Passed |
| `npm run lint` | Passed with zero warnings |
| `npm run build` | Passed; static route output includes `/copilot` |

### Backend

Run from `apps/api` with `DJANGO_SETTINGS_MODULE=config.settings.test`:

```text
python manage.py test copilot.tests.test_conversations copilot.tests.test_retrieval_index copilot.tests.test_chunking documents.tests.test_policies documents.tests.test_services documents.tests.test_api --noinput
```

Outcome: 46 tests discovered and passed; 0 failed; 0 skipped. The run covers F-04 conversation behavior, retrieval/indexing, and F-03 authorization policy, service, and API regressions. Its embedded Django system check reported no issues.

| Command | Outcome |
| --- | --- |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` |
| `python manage.py check` | `System check identified no issues (0 silenced)` |

### Native MySQL

The following was attempted using only the available local configuration:

```text
python manage.py test copilot.tests.test_conversation_mysql copilot.tests.test_mysql --noinput
```

Django found 16 tests but no assertion executed because test-database creation failed with MySQL error 1045: access denied for `it_copilot@localhost` using no password. Credentials were not guessed, exposed, or changed. This is an environmental blocker, not a passing or failing test assertion.

Previously accepted native evidence is retained as historical dependency evidence:

- IC-018/PR #23: 24 combined native MySQL F-03/IC-018 migration and concurrency tests passed.
- IC-019/PR #24: 16 native MySQL conversation/retrieval tests passed.

These historical counts are not represented as post-merge reruns.

### Browser verification

Not executed. The repository contains Playwright-based F-01/F-03 specs, but no Copilot browser spec or Playwright configuration, no running application harness, and no required E2E credential variables were available. No new framework, test identity, or credential was introduced for closure. The production build and jsdom component suite are the current UI evidence; they are not a substitute for a real-browser accessibility audit.

### Dependency audit observation

`npm install` audited 489 packages and reported 8 moderate-severity findings, matching the previously recorded limitation. No `npm audit fix`, forced upgrade, or lockfile change was performed.

## 7. Security and authorization evidence

| Boundary | Evidence type | Verification |
| --- | --- | --- |
| Session authentication and CSRF | Code inspection and executed tests | Copilot mutation views use `csrf_protect`; the shared browser client sends credentials and CSRF tokens. Conversation/API and frontend suites passed. |
| Owner isolation | Code inspection and executed tests | Conversation queries require the freshly loaded owner; cross-owner access returns generic not-found behavior. Conversation and F-03 policy/API suites passed. |
| Role and deactivation | Code inspection and executed tests | Conversation and evidence release reload actor lifecycle/role; deactivated or ineligible actors are denied immediately. Retrieval and policy tests passed. |
| Authorized retrieval | Code inspection, executed SQLite tests, accepted native evidence | `release_authorized_evidence()` locks and revalidates actor, document, version, tombstones, existence, length, and digest before materialization. SQLite boundary tests passed; native race evidence remains accepted history. |
| Citation release | Code inspection and executed tests | Server citations contain stable ID, document/version IDs, label, and version sequence; no snippet, key, or path. The UI renders only label/version and creates no download URL. |
| Grounding outcomes | Code inspection and executed tests | Provider-disabled evidence returns references with no synthesized content; no evidence returns explicit insufficient status without generic advice. |
| Expiry and deletion | Code inspection and executed tests | Normal access requires `retention_expires_at > now`; expired/deleted records are generically unavailable. Cleanup revalidates expiry before deletion. |
| Provider/private transfer | Code inspection and accepted task evidence | Independent `COPILOT_PROVIDER_ENABLED` and `COPILOT_PRIVATE_TRANSFER_AUTHORIZED` gates remain required; no transport implementation or credential is present. |
| Infrastructure exclusions | Repository/diff inspection | No AWS, Redis, Celery, vector database, external search, provider SDK, or deployment addition is part of merged F-04. |

No material security or functional defect was identified during this closure verification.

## 8. Provider-disabled boundary

AI-generated synthesis remains unavailable by design. The provider adapter fails closed unless both provider enablement and private-transfer authorization are true and the configured model is allowlisted. The merged MVP installs no provider transport and performs no external provider request. The UI explicitly identifies synthesis as disabled and never fabricates an answer. Any future activation, credential use, model change, or private-document transfer requires a separate PO/SOL authorization and new security verification.

## 9. Accepted limitations

- AI-generated synthesis is disabled.
- Citations are non-clickable pending an approved citation-to-document resolution interface.
- The UI consumes the first bounded conversation page of 25 records.
- No completed real-browser workflow or accessibility audit is available.
- The current dependency set reports 8 moderate npm audit findings pending separately authorized assessment/remediation.
- Native MySQL could not be rerun post-merge without legitimate credentials; accepted IC-018/IC-019 native results remain historical evidence.
- MySQL natural-language FULLTEXT retains stopword and minimum-token behavior.
- Index freshness requires the local worker; security exclusion is enforced independently at evidence release.
- Conversation retention cleanup requires its local scheduled command.

## 10. Deferred enhancements

The following remain deferred and are not represented as implemented:

- Provider activation, credentials, generated synthesis, and private-document transmission.
- Approved citation-to-document navigation.
- Conversation pagination beyond the first 25 records.
- Real-browser authenticated Copilot and assistive-technology verification.
- Dependency vulnerability assessment and controlled upgrades.
- Deployment, AWS, Redis, Celery, vector/embedding search, web search, autonomous agents, tools, attachments, and multimodal behavior.

## 11. Final acceptance matrix

| ID | Feature criterion | Evidence | Result |
| --- | --- | --- | --- |
| F04-AC-01 | Accepted IC-018/019/020 merges are on `main` | Git ancestry and GitHub PR metadata | PASS |
| F04-AC-02 | Authenticated owner-private conversation lifecycle | Code inspection; conversation/frontend tests | PASS |
| F04-AC-03 | F-03-owned authorized evidence boundary | Code inspection; retrieval/policy/service/API tests; historical native evidence | PASS |
| F04-AC-04 | Bounded local retrieval and indexing | IC-018 implementation and executed retrieval tests | PASS |
| F04-AC-05 | References-only and insufficient outcomes | Conversation and frontend tests | PASS |
| F04-AC-06 | Metadata-only citation presentation | Code inspection and frontend tests | PASS |
| F04-AC-07 | Expiry, deletion, owner, role, and deactivation enforcement | Executed backend tests and code inspection | PASS |
| F04-AC-08 | Responsive, race-safe Copilot workspace | 50 frontend tests, typecheck, lint, and production build | PASS with accepted browser-audit limitation |
| F04-AC-09 | Provider and private transfer remain disabled | Code inspection and merged configuration | PASS |
| F04-AC-10 | No unauthorized external infrastructure | Repository inspection | PASS |
| F04-AC-11 | Native post-merge concurrency rerun | Test database unavailable: MySQL 1045, no password | NOT VERIFIED post-merge; accepted historical evidence retained |
| F04-AC-12 | Living documentation and limitations are accurate | Feature record and this closure record | PASS |

## 12. Closure recommendation

The merged F-04 implementation is internally consistent with the ratified MVP contract and passed all executable post-merge frontend, SQLite backend, migration, and system checks. No blocker was identified. SOL may close F-04 with the explicit accepted limitations above and the native post-merge rerun recorded as unavailable rather than passed.

This recommendation does not authorize provider activation, private-data transfer, dependency remediation, deployment, or additional functionality.
