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
| AC-12 | 242 relevant tests run; 46 skipped and 196 passed under SQLite | Passed |
| AC-13–14 | This record; no frontend/external infrastructure | Implemented |

## Known limitations

Provider generation is intentionally unavailable. Reference-only fallback does not summarize documents. Conversation list pagination uses bounded page/size pagination rather than an opaque cursor; ownership prevents cross-user count leakage. Retention cleanup requires scheduled local command execution. Citation integrity does not establish that an eventual generated claim is factually supported; that requires provider-era adversarial validation after separate transfer authorization.

## Review boundary

SOL should verify the exact local implementation, native concurrency, API security, migration, cleanup and regression evidence. No merge or provider activation is implied by this record.

## Test evidence

- Focused IC-019 SQLite service/API tests: 11 passed.
- Complete Copilot SQLite suite: 24 passed, 15 native-only skipped (39 discovered).
- Native MySQL IC-019 concurrency plus IC-018 retrieval regressions: 15 passed.
- Relevant `accounts.tests`, `documents.tests`, and `copilot.tests`: 242 run, 46 skipped, 196 passed under SQLite settings.
- `makemigrations --check --dry-run`: no changes detected.
- Django system check: no issues.

## G2 focused corrections

### G2-F01 — retention cleanup race

The initial cleanup selected expired IDs and then bulk-deleted them, allowing a conversation renewed after selection to be deleted from stale eligibility. Cleanup now preserves its bounded dry-run selection but, in execute mode, locks each candidate under one transaction, reloads its current expiry, and deletes it only when `retention_expires_at <= now` still holds. MySQL uses `select_for_update(skip_locked=True)` where supported, so cleanup avoids waiting on actively renewed rows. The command reports the number actually deleted rather than the stale candidate count.

A deterministic native MySQL regression selects an expired candidate, renews it from a concurrent connection, and then lets cleanup lock and revalidate the stale candidate. The renewed row remains and the deletion result is empty.

### G2-F02 — expired conversation access

Normal list, detail, message submission, and user deletion now require `retention_expires_at > now`. The exact boundary is therefore expired: a conversation with `retention_expires_at == now` is hidden and generically unavailable and cannot be renewed by submitting a turn. Owner isolation remains unchanged. Cleanup uses its separate internal locked path and can legitimately delete boundary-expired records.

Focused service/API tests cover list exclusion, detail/message/delete denial, exact-boundary behavior, non-renewal, and subsequent authorized cleanup deletion.

### Correction verification

- Focused IC-019 correction suite: 13 passed.
- Native MySQL conversation/retrieval suite: 16 passed, including stale cleanup selection versus renewal.
- Relevant regression suite: 242 run, 46 skipped, 196 passed.
- Migration consistency and Django system checks: passed.
