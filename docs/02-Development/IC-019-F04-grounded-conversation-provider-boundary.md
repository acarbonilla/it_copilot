# IC-019 — Grounded Conversation and Provider Boundary

**Status:** Local implementation complete; pending SOL G2 review
**Baseline:** `main` at `aa9048dad5dcccba4fc5aae453b13e5b7c1f3554`
**Provider state:** Disabled; no network transport or private-document transmission

## Scope

IC-019 adds authenticated owner-private conversation persistence and versioned DRF endpoints on the merged IC-018 retrieval foundation. It implements deterministic reference-only and insufficient-evidence outcomes while provider use remains disabled. It does not implement IC-020 UI, credentials, live provider calls, embeddings, or external infrastructure.

## Data model and lifecycle

`CopilotConversation` has a UUID identity, owner, bounded title, activity timestamps and a rolling 30-day expiry. `CopilotMessage` stores ordered USER/ASSISTANT messages, grounding/provider status and server-generated citation metadata. Account deletion cascades conversations; inactive/deactivated identities fail current access checks immediately.

History is capped at 100 messages. Turns lock the fresh actor and owned conversation, retrieve through IC-018, then persist the user/assistant pair and retention update in one transaction. Failure rolls back the whole pair. Concurrent native-MySQL turns serialize on the conversation lock.

## API contract

- `POST /api/v1/copilot/conversations` — create an owned conversation.
- `GET /api/v1/copilot/conversations` — owner-scoped bounded pagination.
- `GET /api/v1/copilot/conversations/{id}` — owned conversation and bounded history.
- `DELETE /api/v1/copilot/conversations/{id}` — delete an owned conversation.
- `POST /api/v1/copilot/conversations/{id}/messages` — submit a question and atomically persist the completed turn.

All mutations are CSRF protected through existing session authentication. Cross-owner direct access returns generic not-found behavior. Questions are normalized and limited to 2,000 characters by IC-018.

## Grounding and citations

The orchestration service calls `retrieve_authorized_evidence()` and does not reproduce document authorization. IC-018 retains the 40-candidate, 8-evidence, 3-per-document and 12,000-token limits plus the F-03 evidence-release linearization point.

Citation IDs are stable UUIDv5-derived server identifiers over released document/version/chunk identity. Responses expose only citation ID, document/version IDs, display label and version sequence. They contain no snippets, keys or paths. Unknown, duplicate or malformed requested citation IDs are rejected. Citation validation proves reference membership, not factual accuracy.

## Provider-disabled behavior

`DisabledByDefaultProviderAdapter` has independent `COPILOT_PROVIDER_ENABLED` and `COPILOT_PRIVATE_TRANSFER_AUTHORIZED` gates, a pinned allowlist, timeout and output bounds. IC-019 installs no network transport. With relevant evidence, assistant content is empty and the response returns authorized references only. Without evidence, it returns `insufficient` with no citations. No generic IT advice or synthesis is fabricated.

Future provider submission must call the guarded retrieval release again; persisted citation metadata is never authorization for later evidence use.

## Retention and recovery

Activity extends expiry by 30 days. `purge_copilot_conversations` reports at most 100 expired conversations by default and deletes only with `--execute`; the hard batch maximum is 256. Cascading deletion removes messages. Operational output contains counts only.

## Acceptance evidence

| Criterion | Evidence | Status |
|---|---|---|
| AC-01–02 | Owner FK, generic denial, locked atomic message pairs | Implemented/tested |
| AC-03–04 | IC-018 retrieval orchestration and deterministic references/insufficient result | Implemented/tested |
| AC-05–06 | Double provider gate, no transport, no-network test | Implemented/tested |
| AC-07 | Stable citation creation and tamper rejection | Implemented/tested |
| AC-08–09 | Fresh identity checks and bounded API/history/retrieval | Implemented/tested |
| AC-10 | Rolling expiry and bounded dry-run-first cleanup | Implemented/tested |
| AC-11 | Native concurrent-turn serialization | Implemented/tested |
| AC-12 | 239 relevant regressions passed; 45 native-only skips under SQLite | Passed |
| AC-13–14 | This record; no frontend/external infrastructure | Implemented |

## Known limitations

Provider generation is intentionally unavailable. Reference-only fallback does not summarize documents. Conversation list pagination uses bounded page/size pagination rather than an opaque cursor; ownership prevents cross-user count leakage. Retention cleanup requires scheduled local command execution. Citation integrity does not establish that an eventual generated claim is factually supported; that requires provider-era adversarial validation after separate transfer authorization.

## Review boundary

SOL should verify the exact local implementation, native concurrency, API security, migration, cleanup and regression evidence. No merge or provider activation is implied by this record.

## Test evidence

- Focused IC-019 SQLite service/API tests: 11 passed.
- Complete Copilot SQLite suite: 24 passed, 15 native-only skipped (39 discovered).
- Native MySQL IC-019 concurrency plus IC-018 retrieval regressions: 15 passed.
- Relevant `accounts.tests`, `documents.tests`, and `copilot.tests`: 239 passed, 45 skipped under SQLite settings.
- `makemigrations --check --dry-run`: no changes detected.
- Django system check: no issues.
