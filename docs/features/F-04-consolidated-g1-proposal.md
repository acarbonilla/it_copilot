# F-04 Consolidated G1 Requirements Contract

**Feature:** F-04 — Copilot
**Gate:** G1 — requirements and development planning
**Status:** Product Owner ratified D1–D14 with mandatory clarifications C1–C4; authoritative F-04 G1 development contract; not IC-018 implementation authorization
**Prepared by:** IC-031
**Planning baseline:** `main` at `fd152d6716320bdde42fc0a5a0d77f32297709b2`

## 1. Authority, ratification, and discovery history

IC-031 initially discovered that the repository contained only a high-level planned capability and task-range mapping. The initial proposal therefore distinguished four requirement classes:

| Class | Meaning |
| --- | --- |
| Existing approved requirement | Already established by an accepted repository source and must be preserved. |
| Proposed F-04 requirement | Initial IC-031 recommendation that required PO ratification before coding. |
| Open PO decision | Material product, privacy, cost, or architecture choice that was open during discovery. |
| Deferred or excluded | Explicitly outside the proposed local MVP boundary. |

The Product Owner subsequently ratified the recommended defaults for D1–D14 without additional conditions. Those decisions, the functional requirements derived from them, the IC-018–IC-020 definitions, and clarifications C1–C4 are now authoritative G1 requirements. Historical references to the initial proposal describe discovery state only. Ratification does not authorize IC-018 execution, provider activation, credentials, or private-document transfer.

### Mandatory SOL clarifications incorporated

- **C1 — Citation integrity:** server-assigned references are validated; unknown, unauthorized, malformed, or unsupported citations are rejected. Unsupported claims are conservatively rejected or become insufficient evidence. Citation validation improves grounding integrity but does not guarantee factual accuracy. Adversarial grounding tests are required.
- **C2 — Immediate security invalidation:** F-03 authorization, active/current version identity, digest, and physical integrity are revalidated before evidence use. Archived, deleted, superseded, corrupt, invalid, or unauthorized evidence is excluded immediately. The 60-second target is normal indexing freshness only and never creates a security exposure window.
- **C3 — Provider-disabled fallback:** when generation is disabled or unavailable, the service may return currently authorized source references without generated answer text. It never substitutes a generic ungrounded model response. F-03 authorization, generic denial, and citation validation still apply.
- **C4 — Living documentation:** TTDM v2.0 uses one primary Markdown task record per meaningful checkpoint by default, plus feature-level updates where necessary. Four separate Markdown files per task are not required.

## 2. Discovery result

### Existing approved requirements

- The MVP capability list includes “Copilot retrieval and OpenAI integration.” It supplies no detailed behavior or acceptance criteria.
- The approved technology direction is Next.js/TypeScript, Django/DRF, MySQL, local Docker Compose, and Git/GitHub.
- F-01 supplies authenticated server-side sessions, CSRF-protected mutations, bounded error conventions, and the Next.js shell.
- F-02 supplies active-account enforcement, IT roles, App Admin separation, controlled security auditing, and immediate deactivation behavior.
- F-03 supplies private, authorized documents; immutable versions; READY/current publication; verified extracted-text artifacts; recovery; and the rule that F-04 may consume content only through an approved interface.
- F-03 authorization permits an active `IT_MEMBER` or `IT_EDITOR` to access owned documents and an active `IT_DOC_ADMIN` to access documents across owners. App Admin alone has no document-content authority.
- F-03 excludes retrieval, chunking, embeddings, ranking, prompt construction, chat, citations, and external AI calls.

### Planning metadata resolved by ratification

- TTDM-WA-001 and the feature registry map F-04 to `feature/copilot` and IC-018–IC-020.
- No IC-018, IC-019, or IC-020 specification exists in the repository.
- The task range was the basis for planning; the titles, scopes, dependencies, criteria, and G2 boundaries below are now ratified.

### Original source gap

Before IC-031 ratification, no approved source defined conversation persistence, retrieval architecture, embeddings, model/provider, external data transfer, citations, freshness, limits, retention, or detailed Copilot role access. D1–D14 now resolve those gaps as the approved F-04 contract.

## 3. Ratified product boundary

F-04 is a private, authenticated, source-grounded IT-support assistant over the caller’s currently authorized READY F-03 documents. It retrieves bounded evidence, generates an answer only from that evidence, and returns server-validated citations. It is not a general web assistant and does not execute document instructions, tools, code, URLs, credentials, or administrative actions.

Ratified local-MVP requirements:

- active `IT_MEMBER` and `IT_EDITOR`: ask against owned active documents;
- active `IT_DOC_ADMIN`: ask against all active documents permitted by F-03;
- App Admin without an eligible IT role: no Copilot content access;
- anonymous, inactive, pending, deactivated, and role-ineligible callers: denied generically;
- local MySQL lexical retrieval first; no vector database or external search service;
- deterministic local chunking and asynchronous indexing through a Django-managed database queue;
- locally persisted conversations with bounded history and a 30-day retention period;
- OpenAI generation behind a disabled-by-default backend adapter, activated only after separate provider-configuration and private-data-transfer authorization;
- no provider-hosted conversation state, file upload, hosted vector store, web search, tool execution, or background API mode.

## 4. Ratified functional requirements

### 4.1 Copilot interaction

| ID | Ratified requirement |
| --- | --- |
| F04-INT-01 | `/copilot` is available only to active eligible IT identities and never relies on hidden frontend controls for authorization. |
| F04-INT-02 | A user can create a conversation, submit a plain-text question, receive a grounded answer with citations, retry a failed turn, review bounded history, and delete an owned conversation. |
| F04-INT-03 | Question input is UTF-8 plain text, trimmed, nonempty, and no more than 2,000 characters. Attachments, HTML execution, Markdown HTML, URLs as tools, and executable content are excluded. |
| F04-INT-04 | The UI has explicit initial, empty, retrieving, generating, success, insufficient-evidence, rate-limited, provider-unavailable, retryable-error, and terminal-error states. Duplicate submission is prevented while a turn is active. |
| F04-INT-05 | Answers are advisory. The UI states that users must verify consequential actions against cited source material. |
| F04-INT-06 | If no authorized evidence meets the retrieval threshold, the service returns a controlled insufficient-evidence response and does not ask the model to invent an answer. |
| F04-INT-07 | A retry creates a separately auditable attempt for the same user turn; it never silently duplicates a successful answer. |

### 4.2 F-03 retrieval interface

F-04 must not import F-03 models to construct ad hoc queries, read `storage_key`, resolve private paths, or open extracted files directly. The ratified F-03-owned service boundary is:

1. `list_indexable_versions(cursor, limit)` — internal indexing authority only; returns opaque document/version IDs, current-version digest, safe timestamps, and lifecycle state for current READY active documents. It returns no path or content.
2. `open_verified_extracted_text(version_id, expected_digest)` — internal indexing authority only; under the F-03 publication guard, revalidates READY/current/active state, tombstone absence, reference identity, file existence, byte length, and SHA-256, then yields a read-only verified handle or bounded stream. It returns no storage key.
3. `authorize_retrieval_candidates(actor, candidates)` — request-time, bounded bulk authorization; reloads actor lifecycle/role and returns only candidates whose document is active, current version and digest still match, and `VIEW_CONTENT` remains allowed. It returns safe citation metadata only after authorization.
4. `current_retrieval_generation()` or a transactional change/outbox feed — lets the indexer identify publication, archive, restore, deletion, and current-version changes without filesystem scanning.

The interface must preserve IC-026 guard ordering and tombstones, IC-027 bounded-work principles, and IC-028 physical-integrity/current-version validation. Failure is closed: unavailable, corrupt, stale, archived, deleted, or unauthorized evidence is excluded and cannot influence generation.

Authorization and integrity revalidation occurs immediately before any retrieved evidence is used, displayed, persisted as a reference, or sent to a provider. Index freshness never substitutes for this check. A document that becomes archived, deleted, superseded, invalid, or unauthorized is excluded on the next evidence use even if its stale index row has not yet been removed.

### 4.3 Chunking and indexing

| ID | Ratified requirement |
| --- | --- |
| F04-RET-01 | Index only the current READY version of active documents. Candidate, failed, cancelled, archived, deleted, stale, corrupt, or physically unavailable versions are absent or invalidated. |
| F04-RET-02 | Chunking is deterministic and versioned. Recommended starting limit: 600 tokens per chunk with 80-token overlap, preserving paragraph boundaries where possible; exact tokenizer/version is stored. |
| F04-RET-03 | A chunk records opaque chunk ID, document/version IDs, ordinal, content digest, token/character counts, index-generation/version, and locally searchable text. Storage of sensitive chunk text in local MySQL was explicitly approved for IC-018 by the PO under ratified D1 and D14; it remains protected document-content storage. |
| F04-RET-04 | A dedicated database-backed index job has deterministic claim order, lease, heartbeat, bounded retries, stale-worker fencing, idempotent upsert, and one active job per version/generation. Redis and Celery are excluded. |
| F04-RET-05 | Index publication is transactional: partial chunks never become searchable. A generation switch makes a complete replacement visible atomically. |
| F04-RET-06 | Publication, archive, restore, deletion, invalid-current recovery, and version replacement enqueue or mark bounded index work transactionally through the approved interface/outbox. |
| F04-RET-07 | Normal freshness target: an accepted F-03 change becomes reflected or explicitly `index_pending` within 60 seconds during normal local worker operation. This target never permits stale evidence to bypass immediate authorization/current-version/integrity revalidation and is not a security exposure window. |
| F04-RET-08 | Reconciliation reports stale/missing/extra index generations and supports dry-run-first bounded repair. It cannot read raw artifacts outside the F-03 service. |

### 4.4 Retrieval and ranking

Ratified MVP architecture: MySQL `FULLTEXT` lexical candidate retrieval over locally stored chunks, followed by deterministic application ranking. This stays inside the approved database boundary and avoids a vector database or external search service.

Ratified query bounds:

- normalized question: maximum 2,000 characters;
- maximum lexical candidates examined: 40;
- maximum authorized chunks supplied to generation: 8;
- maximum chunks from one document: 3 unless fewer documents are available;
- maximum retrieved context: 12,000 input tokens or a lower model-specific safe bound;
- deterministic tie-breaking by score, document ID, version ID, and chunk ordinal;
- minimum score/coverage threshold; below it, return insufficient evidence;
- one bounded authorization revalidation after ranking and immediately before provider submission.

Rank using lexical score plus deterministic phrase/title boosts. Do not use owner identity, secret metadata, filename, or inaccessible-document counts as ranking signals. Do not reveal the existence or number of excluded documents.

Embeddings are not recommended for the first local MVP checkpoint. They would require a model, dimension, storage/index choice, re-embedding lifecycle, cost and external-data decision. A later ratified extension may add embeddings and hybrid ranking without changing the authorization boundary.

### 4.5 Answer generation

| ID | Ratified requirement |
| --- | --- |
| F04-GEN-01 | Generation occurs only on the trusted Django backend through an adapter. Browsers never receive provider credentials or call the provider directly. |
| F04-GEN-02 | The request contains a fixed system contract, the bounded current question, bounded local conversation context, and only request-time reauthorized evidence chunks. |
| F04-GEN-03 | Retrieved text is explicitly delimited as untrusted evidence. Instructions, credentials, links, or tool requests inside it are never executed or promoted to system instructions. |
| F04-GEN-04 | The provider adapter is disabled by default and fails closed when configuration, credential, model allowlist, or PO-approved data-transfer policy is absent. |
| F04-GEN-05 | After separately authorized provider activation, use a backend Responses API foreground request with `store: false`; do not create provider Conversation objects or upload document files. Local state remains authoritative. |
| F04-GEN-06 | Model ID, timeout, input/output ceilings, and spend/rate ceilings are explicit configuration with safe defaults. Output ceiling: 800 tokens; wall-clock timeout: 20 seconds; at most one bounded retry for an eligible transient failure. |
| F04-GEN-07 | Provider timeout, rate limit, authentication failure, invalid response, refusal, and outage map to controlled errors. Raw provider messages, request IDs, prompts, content, and credentials are not returned or logged. |
| F04-GEN-08 | The model must answer only from supplied evidence. Unsupported claims, malformed citations, or missing evidence cause a controlled insufficient-evidence result or response rejection. |
| F04-GEN-09 | No web browsing, code execution, function calling, MCP, remote tool, hosted file, hosted vector store, or autonomous action is enabled in the MVP. |
| F04-GEN-10 | When the provider is disabled or unavailable, the service may return the final currently authorized source references without generated answer text. It never returns a generic ungrounded model answer. |

Official OpenAI documentation currently states that Responses are stored by default unless `store: false`, while provider abuse-monitoring retention and eligibility for modified/zero-retention controls depend on account configuration. Therefore `store: false` is necessary but not a complete no-retention guarantee. See [Conversation state](https://developers.openai.com/api/docs/guides/conversation-state), [Data controls](https://developers.openai.com/api/docs/guides/your-data), and [Safety best practices](https://developers.openai.com/api/docs/guides/safety-best-practices). Provider activation requires a PO-approved data classification and retention decision.

### 4.6 Citations and attribution

- The server assigns citation labels such as `[1]` to the final authorized evidence set; the model never invents document identifiers.
- The response schema separates answer text from citation objects.
- Citation object: `label`, opaque `document_id`, authorized display title, version sequence, and chunk ordinal/anchor. It exposes no storage path, extracted text, owner email, filename, digest, or provider metadata.
- Every substantive supportable answer claim must reference at least one supplied label. Unknown labels cause rejection.
- Unknown, malformed, unauthorized, or server-unassigned labels are rejected. Claims not supportable by the cited evidence are conservatively rejected or produce insufficient evidence.
- Citation validation verifies reference membership, authorization, and support constraints; it does not guarantee that generated statements are factually accurate.
- Opening a citation invokes a fresh F-03 authorization/current-version check. A citation that is no longer authorized becomes unavailable without revealing why.
- Citation snippets are excluded because they duplicate document content in API/browser state. Adding snippets would require a future reviewed contract change.
- Adversarial grounding tests must cover fabricated labels, citation swapping, partial support, contradictory evidence, prompt-injected citation instructions, stale/superseded sources, and answers whose claims exceed the evidence.

### 4.7 Conversations and retention

Ratified conversation contract:

- MySQL stores conversations and messages locally; no provider-hosted state.
- A conversation has one immutable owner and no sharing/transfer.
- Maximums: 100 conversations per user, 100 turns per conversation, 25 conversations per history page, and 20 recent messages included in generation subject to the token budget.
- Retention: 30 days after last activity, followed by explicit bounded purge; user deletion immediately removes normal access and queues purge.
- Store user question, accepted answer, safe citation references, status, model/config version, token/cost counters, and timestamps. Never store assembled prompts, raw provider payloads, API keys, inaccessible evidence, or raw provider errors.
- Deactivation or role loss denies the next request and prevents history/content access. Reactivation does not silently restore a role that was removed.

### 4.8 API contract

Ratified versioned endpoints:

| Method and path | Purpose |
| --- | --- |
| `GET /api/v1/copilot/conversations` | Owner-only bounded conversation list, default 25 and maximum 100. |
| `POST /api/v1/copilot/conversations` | Create an owner-only conversation; CSRF protected. |
| `GET /api/v1/copilot/conversations/{id}` | Owner-only bounded message page and current status. |
| `DELETE /api/v1/copilot/conversations/{id}` | Soft-delete/queue purge; CSRF protected. |
| `POST /api/v1/copilot/conversations/{id}/turns` | Submit one bounded question using an idempotency key; CSRF protected. |
| `POST /api/v1/copilot/conversations/{id}/turns/{turn_id}/retry` | Explicit bounded retry of a failed turn; CSRF protected. |

Success responses use opaque UUIDs, controlled statuses, answer Markdown subset/plain text, and structured citations. A provider-disabled success may contain no answer text and only currently authorized structured source references. Errors use the existing `{ "error": { "code": "...", "message": "..." } }` envelope. Safe codes include `authentication_required`, `permission_denied`, `not_found`, `invalid_request`, `conflict`, `rate_limited`, `index_pending`, `insufficient_evidence`, `provider_unavailable`, and `service_unavailable`. Cross-owner and missing IDs remain generically indistinguishable.

### 4.9 Frontend and accessibility

- Replace the Copilot “Coming soon” placeholder only after the API is accepted.
- Provide responsive conversation list, new-conversation action, message transcript, question composer, citations, retry/delete controls, and explicit service states.
- Render answer text through a strict safe Markdown subset or plain text; raw HTML is disabled and links are non-executable unless separately reviewed.
- Use semantic landmarks, labeled controls, keyboard-operable history and citations, visible focus, status announcements with appropriate `aria-live`, non-color-only states, and WCAG 2.1 AA contrast targets.
- Do not place questions, answers, document text, citations, provider IDs, credentials, or CSRF values in URLs, analytics, console logs, SSR output for another user, or persistent browser storage.

### 4.10 Security, privacy, and audit

- Reload identity and roles at each request; session presence alone is insufficient.
- Apply F-03 authorization both before candidate content is selected and immediately before provider submission.
- Treat questions, conversations, answers, chunks, citations, and retrieved text as sensitive document content.
- Enforce per-user request limits and one active generation per conversation: 10 turns/minute and 100 turns/day per user. Provider activation additionally requires a configured monetary spend ceiling under D3/D9.
- Prompt injection defenses are layered: no tools, instruction/data separation, bounded inputs, fixed system policy, evidence-only output, citation validation, output sanitization, and adversarial testing. They are not represented as a perfect classifier.
- API key comes only from a server environment/secret mechanism, is never stored in MySQL or returned to clients, and is revocable/rotatable. Startup/health output reveals only configured/unconfigured state.
- Use a privacy-preserving stable safety identifier only if provider use is ratified; do not send email or database IDs directly.
- Critical audits are required for conversation deletion, index repair/publication, provider-configuration changes if runtime administration exists, and security-relevant denial/abuse events. Ordinary questions/answers and document titles/content are not audit fields.
- Logs/metrics contain controlled operation, status, latency bucket, counts, and safe error code only. No question, answer, chunk, title, filename, prompt, provider response, token, cookie, key, path, or exception text.

## 5. Architecture evaluation

| Option | Benefits | Costs/risks | Recommendation |
| --- | --- | --- | --- |
| MySQL lexical chunk index | Uses approved infrastructure; transactional invalidation; native backup/concurrency; no new service | Chunk text becomes sensitive DB content; lexical recall limits; FULLTEXT behavior needs native-MySQL proof | Ratified MVP architecture under D1/D14 |
| Bounded scan of F-03 extracted files | No duplicate content index | Query cost grows with corpus; weak ranking; repeated private-file reads; difficult latency bound | Reject except tiny diagnostic fallback; not normal request path |
| External/vector database | Stronger semantic retrieval possibilities | New service, credentials, retention, deployment, authorization synchronization, backup, cost | Deferred; requires separate architecture and PO decision |
| External embeddings plus local vector storage | Semantic retrieval without hosted search | External document transfer, model/cost/version lifecycle, MySQL vector limitations or custom index | Defer from first MVP checkpoint |
| Provider-hosted files/vector stores | Simplifies provider retrieval | Duplicates private content externally and changes retention/deletion/authorization boundary | Excluded from the ratified MVP |

Recommended flow:

```text
F-03 READY/current publication
  -> transactional F-03 change marker/outbox
  -> Django-managed F-04 index worker
  -> F-03 verified-text service
  -> deterministic chunks + MySQL FULLTEXT generation

Authenticated question
  -> local conversation/rate checks
  -> bounded lexical candidates
  -> F-03 bulk authorization + current/digest revalidation
  -> evidence threshold
  -> disabled-by-default provider adapter (optional, PO-approved)
  -> citation validation + safe response persistence
  -> authorized API/UI
```

## 6. Ratified PO decision register

The Product Owner ratified every recommended default below. The implications are binding. This decision ratification still does not authorize IC-018 implementation. Provider activation and private-document transmission remain separate execution gates under D3 and D4.

| ID | Ratified decision | Approved selection | Full implementation implications |
| --- | --- | --- | --- |
| D1 — Retrieval | MySQL lexical / bounded scan / new search service | **RATIFIED — MySQL lexical** | Sensitive chunk text is stored in MySQL as document content; native FULLTEXT, authorization, backup, and concurrency testing are required; no new search service. |
| D2 — Embeddings | None initially / provider / local model | **RATIFIED — none initially** | No embedding transfer, model lifecycle, vector storage, or embedding cost in the first MVP. |
| D3 — Generation | OpenAI / retrieval-only / other provider | **RATIFIED — OpenAI adapter, disabled until separately approved configuration and activation** | Requires backend-only credential, pinned model, retention, timeout, spend, failure, and provider-contract controls. Ratification does not activate the provider. |
| D4 — External document transfer | Bounded authorized chunks / prohibited | **RATIFIED — bounded authorized chunks only after a separate private-data transfer gate; otherwise retrieval-only references** | Only immediately reauthorized bounded chunks may be transmitted after explicit activation. `store: false` does not eliminate all abuse-monitoring retention. No transfer occurs under IC-018. |
| D5 — Model/version | Dynamic / pinned allowlist | **RATIFIED — server allowlist with pinned model and reviewed upgrades** | Quality, context, cost, reproducibility, and evaluation baselines are version-controlled and re-reviewed on change. |
| D6 — Conversation persistence | None / local 30 days / other | **RATIFIED — local MySQL, 30 days, owner deletion** | Conversation content is sensitive and requires schema, purge, backup, authorization, and deletion evidence. |
| D7 — Citation contract | Attribution / attribution plus snippets | **RATIFIED — attribution without snippets** | Minimizes browser duplication; citations are server-assigned, reauthorized, validated, and never represented as a factual-accuracy guarantee. |
| D8 — Freshness | Synchronous / async / manual | **RATIFIED — asynchronous index, visible pending, 60-second normal target** | Requires worker/outbox and stale-index handling. Immediate evidence revalidation prevents any 60-second security window. |
| D9 — Resource/cost ceilings | Unbounded / configured bounds | **RATIFIED — the question, candidate, context, output, rate, retry, and daily ceilings in this contract** | Prevents abuse and surprise cost and defines controlled limit/failure behavior. |
| D10 — Authorized roles | F-03 matrix / broader access | **RATIFIED — F-03 content matrix** | Preserves owner-private access, `IT_DOC_ADMIN` scope, immediate lifecycle/role effects, and App Admin separation. |
| D11 — Failure fallback | Insufficient evidence / references / generic answer | **RATIFIED — insufficient evidence or authorized source references; never a generic ungrounded answer** | Preserves grounding, generic denial, citation safety, and useful provider-disabled behavior. |
| D12 — Moderation/reporting | Provider plus local / local-only / none | **RATIFIED — provider moderation when separately activated plus a local human report path** | Provider moderation follows D4 transfer/retention gates; local reporting exists regardless of provider state. |
| D13 — Deletion/retention | Immediate denial plus bounded purge / other | **RATIFIED — immediate denial plus 30-day bounded purge** | Requires purge jobs, backup expectations, user messaging, and deletion evidence. |
| D14 — Index content protection | Sensitive MySQL content / field encryption / no persistence | **RATIFIED — treat MySQL chunks as document content** | Database access, backup, logging, audit, authorization, and incident controls must protect chunks as private document content. |

## 7. Ratified task plan

The repository maps F-04 to IC-018–IC-020. The following titles, scopes, dependencies, acceptance criteria, evidence, and G2 boundaries are ratified. A separate execution authorization is still required before each task begins.

### IC-018 — Authorized Retrieval Index and F-03 Service Boundary

**Objective:** Create the explicit F-03 retrieval service, deterministic local chunk index, asynchronous freshness/invalidation, and bounded authorized ranking without external AI.

**Dependencies:** Accepted F-01–F-03; ratified D1, D2, D8, D10, and D14.

**Scope:** service contract; chunk/index/job schemas; MySQL FULLTEXT; worker; outbox/change marker; reconciliation; bounded retrieval service; no generation or chat UI.

**Acceptance criteria:**

1. F-04 obtains text only through the approved verified F-03 service and never sees paths/storage keys.
2. Only active current READY physically valid versions become searchable.
3. Chunking is deterministic/versioned and bounded; index publication is atomic/idempotent.
4. Publish/replace/archive/restore/delete/recovery races cannot yield unauthorized or stale retrieval; the 60-second normal freshness target never delays security invalidation.
5. Candidate work, query length, batches, chunks, context, retries, and reconciliation are bounded.
6. Request-time bulk authorization reloads actor state and immediately revalidates current version, digest, integrity, and visibility before content is used or leaves the retrieval layer, regardless of index freshness.
7. App Admin-only, cross-owner, inactive, deleted, archived, stale-version, corrupt-artifact, and missing-index cases fail closed without existence leakage.
8. Native MySQL tests prove FULLTEXT behavior, job claims, generation switch, concurrent invalidation, rollback, and constraints.
9. Logs/audits contain no content, filename, title, path, question, or raw exception.

**Required evidence:** unit/property tests for chunk boundaries; native MySQL migration/FULLTEXT/concurrency tests; authorization matrix; mutation races; artifact failures; work-bound instrumentation; F-03 regression suite; one primary IC-018 checkpoint record plus necessary feature updates; SOL G2 before IC-019 integration.

### IC-019 — Grounded Conversation and Provider Boundary

**Objective:** Add owner-private conversations, grounded-answer orchestration, provider adapter, citation validation, controlled failures, and DRF contracts.

**Dependencies:** Accepted IC-018; ratified D3–D7, D9–D13; approved provider credential/data policy.

**Scope:** conversation/message/attempt schema; local history; turn orchestration; provider adapter; rate/cost limits; citations; API; retention/purge; no final UI beyond contract fixtures.

**Acceptance criteria:**

1. Conversation ownership, active identity, CSRF, generic direct-ID denial, and deactivation are enforced server-side.
2. Questions/history/context/output/concurrency/rate/retry/retention are bounded and transactionally consistent.
3. No provider request occurs without sufficient request-time-authorized evidence.
4. Adapter is backend-only, disabled by default, credential-safe, timeout-bounded, and uses ratified storage/retention settings.
5. Prompt/data separation, no-tools policy, injection tests, and evidence-only instructions are enforced.
6. Citations are server-mapped and validated; unknown, unauthorized, malformed, or unsupported citations and claims are conservatively rejected or become insufficient evidence. Tests prove validation boundaries without claiming factual-accuracy guarantees.
7. Provider failures produce controlled states with no raw payload/log leakage or duplicate billing attempts beyond policy.
8. Deletion immediately denies access and bounded purge removes local content according to ratified retention.
9. Audit/log/metric schemas contain only controlled non-content fields.
10. Mock-provider tests are deterministic; adversarial grounding covers fabricated/swapped citations, unsupported claims, contradictory evidence, injection, and stale authorization. Any live-provider test uses synthetic nonprivate data and separate explicit authorization.
11. Provider-disabled or unavailable operation may return currently authorized validated source references without answer text and never returns a generic ungrounded answer.

**Required evidence:** API/CSRF/auth tests; prompt-injection and adversarial-grounding corpus; citation mutation/property tests; provider-disabled reference fallback; provider timeout/rate/error mocks; transaction/audit rollback; concurrency/idempotency; retention/purge; secret/log scans; native MySQL tests; one primary IC-019 checkpoint record plus necessary feature updates; SOL G2 before UI integration.

### IC-020 — Copilot UI, Integrated Security, and F-04 Acceptance

**Objective:** Deliver the accessible Copilot UI and prove complete F-04 integration, privacy, recovery, and regression behavior.

**Dependencies:** Accepted IC-018 and IC-019.

**Scope:** `/copilot` UI; history and composer; citations; state/retry/delete UX; accessibility; browser workflows; integrated security/load bounds; feature finalization.

**Acceptance criteria:**

1. Eligible users can create, ask, review, retry, cite, and delete through accessible bounded workflows.
2. Loading, empty, insufficient-evidence, authorized-source-only fallback, index-pending, rate-limit, provider failure, retry, and deactivation states are accurate and safe.
3. Frontend never stores or logs sensitive questions, answers, evidence, provider IDs, credentials, or CSRF values.
4. Citation navigation reauthorizes and cannot expose stale/cross-owner documents.
5. Real-browser tests cover owner, IT_DOC_ADMIN, App Admin denial, cross-owner denial, deactivation, immediate stale-evidence invalidation, prompt injection, provider-disabled authorized-source-only fallback, retry, and deletion.
6. Full backend/native-MySQL/frontend/type/lint/build/browser/security suites pass at the exact feature head.
7. Synthetic-marker scans cover database audit fields, server/worker/Next logs, SSR, URLs, browser storage, and console.
8. Recovery/reindex procedures, cost/resource ceilings, accepted limitations, exact commits, and living records are complete.

**Required evidence:** component/API-contract tests; WCAG-oriented checks; production build; installed-Chrome Playwright; native MySQL integrated races; F-01/F-02/F-03 regressions; content/secret scans; load-bound instrumentation; one primary IC-020 checkpoint record plus necessary feature updates; SOL final G2 and feature integration review.

## 8. Review and integration sequence

| Batch | Task | Gate |
| --- | --- | --- |
| A — retrieval foundation | IC-018 | D1–D14 ratified; separate IC-018 execution authorization required; SOL G2 on exact head before generation work |
| B — grounded service/API | IC-019 | Separate provider activation/private-transfer authorization required; SOL G2 before UI integration |
| C — UI and integrated acceptance | IC-020 | SOL final G2; recovery checkpoint; PO exact-head feature merge authorization |

Following TTDM v2.0 clarification C4, each meaningful checkpoint maintains one primary Markdown task record by default and updates the feature record where necessary. Additional records are created only when they materially improve traceability, not as a mandatory four-file pattern. Feature finalization occurs only after all three tasks are verified and complete integration/security evidence is accepted. Routine formatting, Git hygiene, and administrative closeout are not separate implementation tasks.

## 9. Deferred and excluded capabilities

- Vector database or external search service.
- Provider-hosted vector stores, file uploads, conversation objects, or persistent threads.
- Web browsing, autonomous agents, tool/function execution, shell/code execution, URL fetching, ticket changes, account actions, or credential retrieval.
- Image/audio input, OCR, voice, realtime, attachments, multimodal answers, and fine-tuning.
- Cross-user/shared conversations, public links, exports, analytics, feedback training, and organization-wide corpora beyond F-03 authorization.
- F-05 credential vault access, deployment/cloud architecture, Redis, Celery, AWS, and production operations.

## 10. Ratification result and execution boundary

The Product Owner ratified D1–D14, C1–C4, and the IC-018–IC-020 contract. F-04 G1 is therefore complete and ready for SOL verification. IC-018 implementation remains unauthorized until a separate execution instruction. Provider activation, credentials, live-provider testing, and private-document transfer remain blocked until their separate IC-019-era authorization gates are satisfied.
