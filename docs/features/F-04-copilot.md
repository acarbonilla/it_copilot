# F-04 — Copilot

**Status:** IC-018, IC-019, and IC-020 merged; post-merge verification complete and pending SOL closure review
**Closure branch:** `docs/f04-post-merge-closure`
**Ratified task range:** IC-018–IC-020
**Dependency baseline:** F-01, F-02, and F-03 accepted on `main`

## Purpose

F-04 is the ratified MVP capability for authenticated Copilot retrieval with separately gated provider integration. IC-018 provides the merged local retrieval foundation. IC-019 adds owner-private conversations, reference-only grounded fallback, citation validation, retention, and a disabled provider interface. IC-020 provides the merged authenticated, responsive Copilot workspace and its integrated frontend security behavior.

The authoritative contract is [F-04 Consolidated G1 Requirements Contract](F-04-consolidated-g1-proposal.md). It preserves IC-031 discovery history and records PO ratification of D1–D14 plus clarifications C1–C4. IC-019 adds local conversation endpoints but no credential, provider network call, or private-data transfer.

## Existing boundaries inherited by F-04

- F-01: server-side session authentication, CSRF, API error conventions, and Next.js shell.
- F-02: active-account checks, IT roles, App Admin separation, controlled auditing, and immediate deactivation denial.
- F-03: owner-private/cross-owner IT authorization, active/current/READY document state, verified extracted artifacts, and publication/recovery protections.
- F-04 must consume F-03 through an approved service. Storage keys, paths, artifact tables, and raw private files are not an integration API.

## Ratified scope

- Authenticated owner-private conversations and bounded history.
- Deterministic chunking, MySQL lexical index, bounded ranking, and asynchronous freshness.
- Request-time F-03 authorization before evidence can influence a response.
- Evidence-grounded answers with server-validated citations, conservative unsupported-claim rejection, and explicit insufficient-evidence behavior; citation validation is not a guarantee of factual accuracy.
- Backend-only, disabled-by-default provider adapter governed by the ratified model, credential, data-transfer, retention, and cost contract; activation remains separately authorized.
- Provider-disabled or unavailable fallback may return currently authorized validated source references without generated answer text; it never returns a generic ungrounded response.
- Immediate request-time F-03 authorization/current-version/integrity revalidation excludes invalid evidence regardless of the normal 60-second indexing target.
- Accessible Next.js chat UI and versioned DRF contracts.
- Prompt-injection resistance, controlled audit/log data, retention/deletion, deactivation, and complete regression evidence.

## Ratified checkpoints

| Task | Ratified title | Gate |
| --- | --- | --- |
| IC-018 | Authorized Retrieval Index and F-03 Service Boundary | Retrieval architecture, native MySQL, authorization, freshness, and race G2 |
| IC-019 | Grounded Conversation and Provider Boundary | Provider/privacy/cost ratification and grounded API G2 |
| IC-020 | Copilot UI, Integrated Security, and F-04 Acceptance | Browser/integration/security G2 and feature finalization |

These titles, scopes, dependencies, criteria, and G2 boundaries are ratified. IC-018, IC-019, and IC-020 are merged on `main`. Their implementation decisions and historical test evidence remain recorded in their task documents and PRs.

## Recommended architecture

Use a local MySQL FULLTEXT chunk index and Django-managed database job queue first. Do not introduce Redis, Celery, a vector database, or external search. Keep F-03 as owner of artifact integrity and authorization through a narrow verified-text and candidate-authorization service.

After separate provider activation and private-transfer authorization, use a trusted backend adapter with bounded, reauthorized context, local conversation state, `store: false`, no provider-hosted conversations/files/vector stores, no tools, controlled timeouts/retries, and server-validated citations. Provider configuration remains disabled until those execution gates are recorded.

## Ratified decisions and remaining execution gates

The PO ratified D1–D14 exactly as recorded in the contract and subsequently authorized IC-018 local implementation. IC-018 now provides an F-03-owned verified-text boundary, deterministic local chunks, transactional MySQL FULLTEXT generations, a database worker, request-time reauthorization, and bounded reconciliation. Provider activation, credentials, live-provider testing, and private-document transfer remain separately gated and are not part of IC-018.

## Accepted dependency limitations

F-03 remains limited to local Windows/NTFS and native MySQL, report-only purge, retained quarantine, and coordinated backup/restore. F-04 planning does not remove or silently expand those boundaries.

## Exclusions

No web search, autonomous agents, tool execution, credential-vault access, hosted vector store, external search service, attachment/multimodal interface, deployment work, AWS, Redis, Celery, or F-05 behavior is authorized.

## Accepted MVP limitations

- AI-generated synthesis remains disabled; references are returned without generated answer text.
- Citations remain non-clickable pending an approved document-resolution interface.
- The workspace displays the first bounded conversation page of 25 records.
- No real-browser accessibility audit has been completed; component-level accessibility evidence is retained.
- The current lockfile installation reports eight moderate npm audit findings; no automatic upgrade or audit fix has been authorized.
- Native MySQL post-merge rerun remains unavailable without legitimate local credentials. Accepted IC-018 and IC-019 native evidence remains historical dependency evidence and is not represented as a new run.

## Closure record

Post-merge commands, security evidence, limitations, and the final acceptance matrix are recorded in [F-04 Post-Merge Verification and Closure](../02-Development/F-04-post-merge-verification-and-closure.md).

The provider and private-document-transfer gates remain disabled. Provider activation, deployment, dependency remediation, broader pagination, citation resolution, and other enhancements require separate authorization.

Recommended disposition: **F-04 post-merge verification complete; ready for SOL closure review**. This documentation does not itself declare PO acceptance or authorize deployment.
