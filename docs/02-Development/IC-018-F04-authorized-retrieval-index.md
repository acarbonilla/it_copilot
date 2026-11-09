# IC-018 — Authorized Retrieval Index and F-03 Service Boundary

**Status:** Local implementation complete; pending SOL G2 review
**Baseline:** `fd152d6716320bdde42fc0a5a0d77f32297709b2` planning baseline; implementation isolated on the existing working tree
**External provider state:** Disabled and out of scope

## Scope and architecture

IC-018 implements the ratified local retrieval foundation only. F-04 never opens an artifact or consumes a storage key. `documents.retrieval` owns bounded version discovery, verified extracted-text access, request-time authorization/integrity revalidation, and a content-free transactional change outbox.

Deterministic `paragraph-window-v1` chunking uses the explicit `unicode-regex-v1` tokenizer, at most 600 tokens per chunk, and 80-token overlap. MySQL stores sensitive chunk text in unpublished/published generation records and exposes it only through the internal retrieval service. A MySQL FULLTEXT index supplies at most 40 lexical candidates; application ranking returns at most 8 chunks, 3 per document, and 12,000 tokens.

## Schema and worker

- `DocumentRetrievalChange` records READY publication and lifecycle/integrity invalidations in the same transaction as the F-03 change.
- `RetrievalIndexJob` has deterministic claim order, one nonterminal slot per version, 60-second leases, heartbeat, three bounded attempts, retry delay, and stale-worker fencing.
- `RetrievalIndexGeneration` publishes a complete generation atomically and permits only one searchable generation per document.
- `RetrievalChunk` stores opaque IDs, version/document identity, ordinal, digest, counts, and sensitive searchable text. It is not registered with an admin/API serializer and is never logged.
- `process_retrieval_index` processes at most 100 jobs by default (maximum 256). `reconcile_retrieval_index` is bounded and dry-run by default; `--repair` is explicit.

## Security and concurrency contract

Index construction reads verified text only through F-03. Publication and request-time evidence validation take the F-03 artifact-publication guard before document/version locks and validate lifecycle, current version, original and extracted tombstones, existence, byte length, and SHA-256. Retrieval first limits candidates to currently visible documents, reloads actor state, then bulk reauthorizes at most 40 candidates. Archive, deletion, replacement, corruption, deactivation, role loss, or ownership denial therefore excludes evidence at its authorization linearization point even before asynchronous cleanup.

Generation rows remain non-searchable until all chunks are inserted in the same transaction. A failed insertion rolls back both generation and chunks. Obsolete generations may remain for bounded cleanup but cannot influence retrieval.

## G2-C01 blocking-findings correction

### G2-F01 — evidence-release linearization

G2-EV01 found that F-03 authorization completed before F-04 constructed its final immutable evidence objects. A lifecycle or actor mutation could therefore commit after authorization but before evidence returned.

`documents.retrieval.release_authorized_evidence()` now owns the complete release boundary. It acquires the artifact-publication guard first, then locks the freshly reloaded actor row, candidate document rows, and version rows. It revalidates role/lifecycle, ownership, active/current/READY state, version/digest, tombstones, and both artifacts' existence, length and SHA-256. The bounded internal materializer constructs the final `RetrievalResult` while all those locks and the guard remain held. Its return is the authorization linearization point.

Archive, delete, version replacement, role removal, deactivation and index publication serialize after that point. A revocation that begins or commits after release may make the already returned result historical, as with any linearizable read, but it cannot move the result's authorization point backward or alter the immutable evidence already released. Callers must not cache/reuse evidence for a later provider operation; a later use requires a new release operation.

Native MySQL event-coordinated tests hold execution inside the materializer and prove each competing mutation remains blocked until release. The tests use bounded events rather than sleep-based race assumptions. Corrupt source material continues to fail before materialization.

### G2-F02 — resumable FULLTEXT migration

G2-EV01 found that the original non-atomic initial migration could leave tables created but the migration unrecorded after a FULLTEXT failure, causing duplicate-table errors on rerun.

Schema creation now remains in transactional `0001_initial`. MySQL FULLTEXT DDL is isolated in non-atomic `0002_retrieval_chunk_fulltext`. Before accepting or creating the index, the migration validates the chunk table, required columns, searchable-text type, critical unique/check constraints, and any existing index definition. The expected post-DDL/pre-migration-record state is idempotent: rerun validates the existing exact FULLTEXT index and succeeds. An incompatible same-name index, missing/incompatible column, or missing critical constraint fails clearly and requires manual schema review; it is never silently ignored or dropped.

Native tests simulate failure immediately after FULLTEXT DDL, rerun the recovery function twice, and verify the final index. A separate test creates an incompatible same-name index and verifies explicit rejection. Fresh test-database migration verifies `0001` followed by `0002` from an empty schema.

## Acceptance evidence

| Criterion | Implementation evidence | Status |
|---|---|---|
| AC-01–02 | `documents/retrieval.py`; guarded verified stream and eligibility validation | Implemented |
| AC-03 | `copilot/chunking.py`; deterministic tokenizer, bounds, overlap and digests | Implemented/tested |
| AC-04 | `copilot/indexing.py`; one-transaction generation/chunk publication | Implemented/tested |
| AC-05 | Claim, heartbeat, retry, lease and fencing paths | Implemented/tested |
| AC-06 | Settings and hard service limits (256/100/40/8/3/12,000) | Implemented/tested |
| AC-07–08 | Guarded F-03 authorize-and-materialize release plus native revocation races | Implemented/tested |
| AC-09 | Resumable MySQL FULLTEXT migration, definition validation and concurrency | Implemented/tested natively |
| AC-10 | Internal-only models, generic errors and content-free diagnostics | Implemented/tested |
| AC-11 | Relevant F-01/F-02/F-03/F-04 suites | 227 passed/44 skipped with SQLite test settings |
| AC-12–13 | This record; no provider or Git integration action | Implemented |

## Validation log

- Focused `copilot.tests` on SQLite test settings: 13 passed; 6 MySQL-only tests skipped when included.
- Relevant `accounts.tests`, `documents.tests`, and `copilot.tests`: 227 passed, 44 skipped on SQLite test settings.
- Native MySQL `copilot.tests.test_mysql`: 14 passed. This includes fresh migration, partial-DDL recovery/rerun, incompatible-index rejection, FULLTEXT definition verification, six evidence-release races, claim concurrency, atomic rollback, lease fencing and retry bounds.
- Combined native MySQL F-03 publication/quarantine concurrency plus IC-018 suite: 24 passed.
- Django system check: passed.
- Migration consistency (`makemigrations --check --dry-run`): passed.

## Known limitations and recovery

MySQL natural-language FULLTEXT has engine stopword and minimum-token behavior; short IT terms may not match and no semantic fallback is introduced. SQLite's portable matcher exists for deterministic unit testing only and is not production proof. Normal index freshness depends on the local worker running within the 60-second target; security exclusion does not depend on that target. Reconciliation scans a caller-bounded document page and repair must be explicitly selected.

Unexpected partial schema states are not automatically repaired. If `0002` reports an incompatible table, column, constraint or index, stop and inspect the schema against the migration definition; do not fake the migration, drop data or mark it applied. Only the explicitly validated state where `0001` is complete and the exact FULLTEXT index is absent or already present is automatically recoverable.

For index-data recovery, run `reconcile_retrieval_index --limit 100` first, inspect only opaque identifiers/error codes, then run with `--repair` if authorized. Run `process_retrieval_index --max-jobs 100` to consume repaired work. No command reads artifacts outside the F-03 service.

## Changed-file inventory

The implementation changes Django settings; F-03 retrieval/outbox integration and its migration; the `copilot` app, schema, migrations, worker, retrieval, reconciliation, commands and tests; this record; and the two authoritative F-04 documents. No frontend, provider, conversation, or deployment implementation is included.

## Review boundary

SOL must verify native MySQL FULLTEXT/migration/concurrency evidence and relevant regressions before G2 acceptance. IC-019, provider activation, credentials, and private-document transfer remain unauthorized.
