# F-03 Consolidated G1 Requirements Proposal

**Status:** Product Owner ratified with mandatory SOL clarifications finalized
**Feature:** F-03 - Documentation Management
**Task range:** IC-009 through IC-017
**Proposal baseline:** `a96b396a2efe35713a549b7e4e3e7daf5d2f3c50`
**Feature branch:** `feature/documentation-management`
**SOL planning review:** PASS, review `5693729644`
**SOL G1 review:** `5693795827`
**Product Owner decision:** Ratified IC-009 through IC-017, Decisions 1-15, and bounded Batches A-E, subject to the four exact-head SOL G2 PASS boundaries

The task definitions, decisions, limits, and acceptance criteria originated as proposals at `5016a7b50edcfc8d67824e13bbb647a116fdbe79`. The Product Owner has ratified them with the lifecycle, parser-isolation, and extracted-text clarifications below. Existing F-01/F-02 contracts remain authoritative where referenced. F-03 implementation may proceed only batch-by-batch and must stop for SOL G2 PASS at each stated exact-head boundary.

## Proposed product boundary

F-03 provides private, role-controlled document ingestion, metadata management, asynchronous text extraction, processing status, safe download, and local recovery operations. It produces normalized document text and processing metadata for later consumers.

F-03 does **not** provide semantic chunking for retrieval, embeddings, vector storage, ranking, retrieval-augmented generation, prompt construction, chat, citations in Copilot answers, or external AI calls. Those are future F-04 concerns. F-04 may later consume only the accepted F-03 service contract; it must not read private artifacts or tables by undocumented coupling.

## Proposed task mapping

### IC-009 - Document Domain and Lifecycle

**Proposed objective:** Establish the MySQL-backed document aggregate, lifecycle, immutable ownership, version control, constraints, and atomic audit vocabulary on which all F-03 paths depend.

**Proposed dependencies:** IC-002 persistence/API foundation; IC-003 user roles and ownership policy; IC-008 audit infrastructure.

**Proposed acceptance criteria:**

| ID | Proposed criterion |
| --- | --- |
| IC-009-AC-01 | Forward Django migrations create document, document-version, processing-job, and extracted-text metadata structures with UUID identifiers, foreign keys, uniqueness/check constraints, and required indexes on native MySQL. |
| IC-009-AC-02 | Document visibility state is `ACTIVE`, `ARCHIVED`, or `DELETED`; each immutable version independently has processing state `STAGED`, `QUEUED`, `PROCESSING`, `READY`, `FAILED`, or `CANCELLED`. Only the finalized transition tables are accepted, and invalid transitions fail without partial state or audit writes. |
| IC-009-AC-03 | A document has one immutable owner, a monotonically increasing metadata revision, one current binary version, timestamps, safe display metadata, and no user-controlled storage path. |
| IC-009-AC-04 | Updating metadata requires the expected revision; stale updates return a generic conflict and do not overwrite newer data. |
| IC-009-AC-05 | Archive is reversible; soft deletion is terminal to users and removes normal access immediately. Physical purge is an explicit maintenance/reconciliation action, not IC-024 account deletion. |
| IC-009-AC-06 | Create, lifecycle change, archive, restore, and soft-delete mutations write controlled, non-content audit events atomically; required audit failure rolls back the mutation. |
| IC-009-AC-07 | `makemigrations --check`, migration apply/check, schema constraints, rollback behavior, and model-drift checks pass on native MySQL. |

### IC-010 - Document Authorization and Ownership

**Proposed objective:** Enforce deny-by-default, server-side document permissions consistently in services, querysets, APIs, downloads, and processing requests.

**Proposed dependencies:** IC-003; IC-007 account lifecycle; IC-008; IC-009.

**Proposed acceptance criteria:**

| ID | Proposed criterion |
| --- | --- |
| IC-010-AC-01 | The authorization matrix in this proposal is implemented in a shared policy/service boundary and enforced before document metadata, content, artifact existence, or processing state is disclosed. |
| IC-010-AC-02 | App Admin has no implicit document-content access. App Admin may view operational metadata needed for account/system administration but may not download, preview, edit, process, archive, or delete a document unless separately assigned an eligible IT role and otherwise permitted. |
| IC-010-AC-03 | Owners and authorized IT roles receive only allowed documents in list/query results; direct UUID access cannot bypass object authorization. |
| IC-010-AC-04 | Anonymous, inactive, deactivated, unauthorized, and cross-owner callers receive generic responses that do not confirm document or artifact existence. |
| IC-010-AC-05 | Role downgrade or account deactivation takes effect on the next request, including download and worker-trigger endpoints. |
| IC-010-AC-06 | Authorization denials for sensitive mutations use controlled audit events without titles, filenames, content, paths, or secrets. |
| IC-010-AC-07 | Unit, API, browser, and cross-owner negative tests cover every matrix row, including combined App Admin/IT-role identities. |

### IC-011 - Secure Upload and Private Artifact Storage

**Proposed objective:** Accept bounded PDF, plain-text, and Markdown uploads into private local storage without exposing paths or leaving unsafe partial artifacts.

**Proposed dependencies:** IC-009 and IC-010.

**Proposed acceptance criteria:**

| ID | Proposed criterion |
| --- | --- |
| IC-011-AC-01 | Authenticated, CSRF-protected multipart upload accepts exactly one `.pdf`, `.txt`, or `.md` file, at most 10 MiB and 500 pages for PDF, with a 12 MiB request cap. Empty files, extra files, archives, office formats, executables, encrypted/password-protected PDFs, and malformed payloads are rejected generically. |
| IC-011-AC-02 | Validation uses extension, declared type, signature/content checks, and parser preflight where applicable; client MIME type and filename are never trusted as authority. |
| IC-011-AC-03 | The original filename is normalized only for a user-facing display value, limited to 255 characters, and never used as a path or audit field. |
| IC-011-AC-04 | Binary artifacts are stored outside public/static/media serving roots under a configured private root using server-generated opaque names, exclusive creation, path-containment checks, and least-privilege filesystem access. |
| IC-011-AC-05 | The database stores an opaque storage key, SHA-256 digest, byte length, detected media type, and current version. It does not store absolute paths or raw binary data. |
| IC-011-AC-06 | Artifact creation, database creation, audit, and job enqueue use a documented compensation protocol: any failure leaves no usable document and removes or quarantines the orphan artifact. |
| IC-011-AC-07 | Duplicate content is allowed as a distinct document in the local MVP; digest is integrity metadata, not global deduplication or a cross-owner information oracle. |
| IC-011-AC-08 | Artifact-failure, traversal, symlink/reparse-point, oversize, malformed-content, CSRF, cross-owner, and rollback tests pass on Windows local-MVP storage. |

### IC-012 - Database-Backed Processing Job Lifecycle

**Proposed objective:** Provide a transactional, observable, idempotent MySQL job state machine for asynchronous document processing.

**Proposed dependencies:** IC-009 through IC-011.

**Proposed acceptance criteria:**

| ID | Proposed criterion |
| --- | --- |
| IC-012-AC-01 | Job states are `PENDING`, `RUNNING`, `SUCCEEDED`, `RETRY_WAIT`, `FAILED`, and `CANCELLED`, with explicit allowed transitions and timestamps. |
| IC-012-AC-02 | Enqueue is atomic with the document/version mutation and enforces at most one nonterminal processing job per document version. |
| IC-012-AC-03 | Workers claim jobs atomically on native MySQL using row locking with deterministic ordering; concurrent workers cannot successfully claim the same attempt. |
| IC-012-AC-04 | A claim has a random worker identifier, lease expiry, attempt number, and heartbeat. Default lease is 60 seconds with heartbeat at most every 20 seconds; only the lease owner may complete or extend it. |
| IC-012-AC-05 | A job receives at most three attempts with retry delays of 5 and 30 seconds. Validation/unsupported/encrypted failures are terminal; transient I/O or worker interruption may retry. No unbounded automatic retries occur. |
| IC-012-AC-06 | Reclaiming an expired lease is safe, completion is idempotent, stale workers cannot publish results, and exactly one accepted result is current for a document version. |
| IC-012-AC-07 | Cancellation is permitted before terminal completion; archival/deletion prevents new claims and stale completion cannot resurrect document availability. |
| IC-012-AC-08 | Native MySQL tests prove claim exclusivity, lease recovery, stale-owner rejection, idempotent completion, enqueue uniqueness, retry exhaustion, cancellation races, and transaction rollback. |

### IC-013 - Document Processing Worker and Text Extraction

**Proposed objective:** Run an independently invocable Django-managed worker that safely extracts normalized text and bounded metadata from accepted document formats.

**Proposed dependencies:** IC-011 and IC-012.

**Proposed acceptance criteria:**

| ID | Proposed criterion |
| --- | --- |
| IC-013-AC-01 | A Django management command processes queued jobs without a public inbound endpoint and supports bounded one-shot and continuous local-development modes. |
| IC-013-AC-02 | PDF, UTF-8 plain text, and UTF-8 Markdown produce normalized UTF-8 text, page count where applicable, character count, extractor/version identifier, and content digest. Markdown is treated as text; no embedded scripts, includes, remote resources, or macros execute. |
| IC-013-AC-03 | Extracted text is capped at 2,000,000 characters. Parsing runs in a separately spawned, killable child process with a hard 120-second wall-clock deadline and a 512 MiB private-memory ceiling. On supported Windows local execution, a Job Object contains the parser process tree and enforces memory and kill-on-close; deadline expiry terminates the whole job and waits for exit. If isolation or limits cannot be established, processing fails closed before parsing. A timeout checked only after parser return is noncompliant. |
| IC-013-AC-04 | Output is written to a version-specific private staging artifact and becomes current only in a transaction that revalidates job ownership, lease, document version, document visibility, and current-version relationship. Extracted and staged text are document content, never public metadata. |
| IC-013-AC-05 | Logs and audit records contain only controlled IDs, states, counts, durations, and safe error codes; no document text, filename, storage path, parser exception, or unrestricted metadata is logged. |
| IC-013-AC-06 | Missing/corrupt artifacts, parser crashes, timeouts, worker termination, stale leases, and database failure follow the retry/failure contract and preserve the last valid result. |
| IC-013-AC-07 | Unit, integration, artifact-failure, transaction-rollback, idempotence, and multi-worker tests pass, including synthetic secret scanning of logs. |

### IC-014 - Document Management API

**Proposed objective:** Expose bounded DRF contracts for authorized document listing, metadata, upload, update, processing status, download, archive, restore, deletion, and retry.

**Proposed dependencies:** IC-009 through IC-013; IC-004 session/CSRF conventions.

**Proposed acceptance criteria:**

| ID | Proposed criterion |
| --- | --- |
| IC-014-AC-01 | Versioned JSON endpoints provide paginated list/detail/status and authorized mutations; upload remains multipart and downloads stream through an authorization check. |
| IC-014-AC-02 | List supports bounded page size (default 25, maximum 100), exact lifecycle/owner filters permitted by policy, and deterministic created/title ordering. Full-text or semantic content search is excluded. |
| IC-014-AC-03 | Mutations use session authentication and CSRF, validate expected revision where relevant, and return the established structured generic error envelope. |
| IC-014-AC-04 | Responses never expose absolute/relative storage paths, extracted text to unauthorized actors, parser diagnostics, audit internals, or other owners' metadata. |
| IC-014-AC-05 | Download uses attachment disposition with a sanitized filename, `X-Content-Type-Options: nosniff`, private/no-store caching, and a safe detected content type; PDF is not rendered inline by this feature. |
| IC-014-AC-06 | Retry is an explicit authorized action for a terminal failed current version and produces one new job without duplicating usable jobs. |
| IC-014-AC-07 | API contract, method, pagination, validation, CSRF, authorization, replay/race, streaming, and generic-error tests pass. |

### IC-015 - Document Management User Interface

**Proposed objective:** Provide an accessible Next.js interface for authorized document operations without moving policy enforcement or secrets into the browser.

**Proposed dependencies:** IC-014; IC-005 frontend session shell.

**Proposed acceptance criteria:**

| ID | Proposed criterion |
| --- | --- |
| IC-015-AC-01 | Authorized users can list, filter, paginate, upload, inspect metadata/status, download, edit title/description, archive/restore, delete, and retry only the operations permitted by the server. |
| IC-015-AC-02 | The upload UI validates obvious size/type errors for usability but treats server validation as authoritative and reports generic safe failures. |
| IC-015-AC-03 | Processing status updates by bounded polling no faster than every five seconds while visible, stops at terminal state, and does not create jobs or duplicate mutations. |
| IC-015-AC-04 | No binary content, extracted text, storage key/path, job lease, or sensitive response is written to localStorage, sessionStorage, IndexedDB, URL query/fragment, analytics, or client logs. |
| IC-015-AC-05 | App Admin-only users see operational metadata only and no content/download controls; combined-role users receive only their IT-role capabilities. |
| IC-015-AC-06 | Keyboard operation, visible labels/focus, status announcements, confirmation for destructive actions, stale-revision conflict handling, and responsive MVP layouts are covered. |
| IC-015-AC-07 | Frontend unit tests, TypeScript, ESLint, production build, real-Chrome Playwright workflows, storage scans, and browser-console scans pass. |

### IC-016 - Reconciliation, Recovery, and Operator Controls

**Proposed objective:** Provide safe, dry-run-first local operations for detecting and repairing stale jobs and artifact/database inconsistencies without exposing content or expanding production scope.

**Proposed dependencies:** IC-009 through IC-014.

**Proposed acceptance criteria:**

| ID | Proposed criterion |
| --- | --- |
| IC-016-AC-01 | Management commands report stale leases, missing artifacts, digest/size mismatches, orphan artifacts, orphan extracted results, and purge-eligible soft-deleted records using controlled IDs only. |
| IC-016-AC-02 | Commands are dry-run by default; mutation requires `--execute` and an explicitly identified active, activated App Admin audit actor. App Admin authority to run recovery does not grant document-content access. |
| IC-016-AC-03 | Execution takes the required lifecycle/row locks, revalidates eligibility, is idempotent, operates in bounded batches, and records actor-attributed audit events atomically with database changes. |
| IC-016-AC-04 | Stale jobs may be returned to retry/failure according to IC-012. Missing/corrupt artifacts mark the current version failed. Orphan artifacts are quarantined before separately approved deletion; no broad recursive delete is used. |
| IC-016-AC-05 | Soft-deleted artifacts become purge-eligible after 30 days, but physical purge requires the explicit command and preserves non-content tombstone/audit integrity. |
| IC-016-AC-06 | Command interruption, repeated execution, actor loss, lock contention, artifact move/delete failure, and audit failure leave recoverable state and are covered by native MySQL and filesystem tests. |
| IC-016-AC-07 | A documented local backup/restore checkpoint covers database plus private artifact root consistency before migration or bulk recovery. No non-test operation is performed during development. |

### IC-017 - F-03 Integrated Security and Acceptance

**Proposed objective:** Demonstrate that the complete F-03 implementation satisfies its contracts, preserves F-01/F-02 invariants, and presents a stable boundary to future F-04.

**Proposed dependencies:** IC-009 through IC-016.

**Proposed acceptance criteria:**

| ID | Proposed criterion |
| --- | --- |
| IC-017-AC-01 | Complete Django tests pass against native Windows MySQL, including migrations/drift, authorization, CSRF, audit fail-closed behavior, lifecycle, concurrency, rollback, idempotence, and artifact failures. |
| IC-017-AC-02 | Complete frontend unit tests, TypeScript, ESLint, production build, and real-Chrome Playwright upload-to-processing workflows pass. |
| IC-017-AC-03 | Synthetic-secret scans find no document content, sensitive filenames, private paths, cookies, CSRF values, job leases, or unrestricted exceptions in SSR output, browser storage, audit data, and development/production/worker logs. |
| IC-017-AC-04 | Security tests cover traversal, symlink/reparse escape, malformed/oversized/encrypted files, authorization races, stale revisions, duplicate jobs, stale workers, unsafe download behavior, and recovery-command misuse. |
| IC-017-AC-05 | F-01 authentication/CSRF and F-02 lifecycle/audit regressions pass; inactive users lose access immediately and required audit failures roll back critical F-03 mutations. |
| IC-017-AC-06 | The documented F-03 service/output contract contains no retrieval, embedding, ranking, prompt, chat, or external-AI behavior and can be consumed by F-04 only through a later approved interface. |
| IC-017-AC-07 | All nine tasks have `specification.md`, `implementation.md`, `test-results.md`, and `review.md`, exact commit/PR inventory, limitations, residual risks, and SOL evidence. |

## Proposed ownership and authorization matrix

Documents are personal by ownership in the local MVP. There is no ad hoc sharing, group workspace, organization-wide visibility, or ownership transfer. `IT_DOC_ADMIN` has controlled organization-wide document management rights; this is an IT content role, distinct from App Admin.

Legend: `Own` = owned documents only; `All` = all documents; `Meta` = non-content operational metadata only; `No` = denied.

| Actor | List/detail metadata | Upload/create | Edit metadata | View extracted text | Download | Process/retry | Archive/restore/delete | Recovery command |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `IT_MEMBER` | Own | Own | Own | Own | Own | Own | Own | No |
| `IT_EDITOR` | Own | Own | Own | Own | Own | Own | Own | No |
| `IT_DOC_ADMIN` | All | Own | All | All | All | All | All | No |
| App Admin only | Meta | No | No | No | No | No | No | Yes, explicit actor |
| App Admin plus IT role | Per IT role | Per IT role | Per IT role | Per IT role | Per IT role | Per IT role | Per IT role | Yes, explicit actor |
| Inactive/deactivated/anonymous | No | No | No | No | No | No | No | No |

`IT_EDITOR` and `IT_MEMBER` intentionally have the same F-03 rights in this proposal because no approved editorial workflow distinguishes them. This avoids inventing elevated cross-owner power. A later feature may add a reviewed distinction. App Admin has **no implicit document-content access**.

## Proposed decision matrix

| # | Decision | Recommended local-MVP default | Alternatives requiring explicit selection | Security/data implication |
| --- | --- | --- | --- | --- |
| 1 | Task definitions | Ratify IC-009 through IC-017 exactly as proposed above | Supply replacement definitions | Prevents implementation against invented scope |
| 2 | Ownership | One immutable personal owner; no sharing or transfer | Shared/team/org documents | Simple object authorization; avoids ambiguous inherited access |
| 3 | Roles and App Admin | Matrix above; App Admin metadata/recovery only, no content | App Admin content access; narrower IT roles | Separation of duties and least privilege |
| 4 | Lifecycle/deletion | Seven states; reversible archive; terminal soft delete; explicit purge after 30 days | Immediate hard delete; indefinite retention | Supports recovery and audit while bounding retained artifacts |
| 5 | Upload contract | One file; PDF/TXT/MD; 10 MiB; PDF <=500 pages; request <=12 MiB | Different formats/limits or batch upload | Bounds parser/resource and request-exhaustion risk |
| 6 | Binary storage | Private contained filesystem outside served roots; DB stores opaque key/digest/size | Database blob; object storage | Local simplicity with path-containment and backup consistency duties |
| 7 | Content safety | Reject archives, Office files, executables, encrypted PDFs; no macro/remote-resource execution; parser preflight | Malware service or sandbox | No external scanner is assumed; strict allowlist reduces exposure but is not malware certification |
| 8 | Processing output | Normalized text plus page/character counts, digest, extractor version, safe status/error code | Rich layout, images, OCR, chunks | Minimizes sensitive derivative data; OCR and retrieval chunking excluded |
| 9 | Job semantics | DB queue; atomic claim; 60s lease/20s heartbeat; max 3 attempts; 5s/30s retry; explicit cancellation/retry | External queue; other lease/backoff | Requires native MySQL concurrency proof and stale-worker fencing |
| 10 | Concurrency/versioning | Optimistic metadata revision; immutable binary versions; one nonterminal job/version | Last-write-wins; pessimistic UI locks | Prevents silent overwrite and duplicate processing |
| 11 | Search/list | Metadata filters/sort/pagination only; no content/semantic search | Database full-text or semantic search | Avoids accidental F-04 scope and content leakage |
| 12 | Audit data | Controlled action, actor/target UUID, outcome, safe reason code; no filename/title/content/path | Permit selected free text | Reduces sensitive data propagation and log injection |
| 13 | Download/preview | Authorized attachment download; no inline preview | Inline PDF/text preview | Attachment plus `nosniff` reduces active-content exposure |
| 14 | Reconciliation | Dry-run-first, explicit App Admin actor, quarantine orphans, bounded/idempotent execution | Automatic destructive cleanup | Human-controlled recovery prevents silent data loss |
| 15 | Performance bounds | Local MVP: 10 MiB/file, 500 PDF pages, 2M extracted characters, 120s/job, list page <=100 | Higher or configurable production limits | Gives deterministic resource tests; production sizing remains deferred |

## Proposed lifecycle and recovery contract

```text
Document visibility (independent of version processing):
ACTIVE <-> ARCHIVED
ACTIVE or ARCHIVED -> DELETED (terminal)

Immutable version processing:
STAGED -> QUEUED -> PROCESSING -> READY
   |         |          |          |
   +---------+----------+--------> FAILED
             +----------+--------> CANCELLED
FAILED or CANCELLED -> explicit authorized retry creates a new job -> QUEUED
```

- Upload does not become a usable version until original-artifact persistence, database record, audit, and enqueue succeed under the compensation protocol. `STAGED` is internal and is not downloadable.
- A replacement upload creates an immutable version and job; it never overwrites an artifact or prior extracted result. The document records a candidate version separately from its current successful version.
- Only successful publication may promote the candidate version to current. Promotion revalidates the lease owner, job attempt, version, document `ACTIVE` state, authorization-independent deletion fence, and candidate relationship in one transaction.
- A failed/cancelled replacement remains diagnostic metadata for authorized users but does not displace the older successful current version. Explicit retry acts on that immutable replacement version.
- Archiving changes only document visibility: it denies ordinary mutation/processing triggers and prevents new worker claims, but preserves versions. Restore returns the document to `ACTIVE`; queued work is not silently restarted and requires an explicit retry/resume action.
- Deletion atomically sets `DELETED`, cancels nonterminal jobs where possible, and fences every later claim/completion/publication. It immediately denies metadata, original artifacts, extracted text, and staged results through normal APIs.
- Job cancellation moves `PENDING`/`RETRY_WAIT` to `CANCELLED` directly or records a cancellation request for `RUNNING`; a running worker must revalidate before publication. Cancellation never changes the current successful version.
- A stale worker may write only to its private attempt staging area. It cannot publish after lease loss, archive, deletion, cancellation, candidate replacement, or job-attempt supersession; rejected staging artifacts are removed or quarantined by reconciliation.
- An older successful version is always reached through the parent document policy. It cannot bypass the document's current authorization, `ARCHIVED`, or `DELETED` state by direct version/artifact identifier.
- Soft deletion immediately denies normal access. Physical purge is delayed 30 days and explicitly executed through IC-016 for original artifacts, extracted text, staged results, and version metadata subject to audit/tombstone retention.
- Database backup, original-artifact storage, extracted-text storage, and any retained staging/quarantine roots are one recovery set. The checkpoint records database transaction position/time plus artifact snapshot identity; restoring only one side requires reconciliation before service use.

## Finalized parser isolation and sensitive-text contract

- The worker process never invokes a document parser in-process. Each attempt spawns a fresh parser child with only the input artifact, format, output staging location, and numeric limits; it receives no session, user, audit, or database credentials.
- On Windows, the parent creates and assigns the parser child to a Windows Job Object before allowing parsing to proceed. The Job Object sets kill-on-close and a 512 MiB process memory limit. The parent enforces a monotonic 120-second wall-clock deadline, terminates the Job Object on expiry, and waits for the process tree to exit before marking timeout. Parser grandchildren inherit containment.
- CPU time is bounded by the wall-clock deadline; input remains limited to 10 MiB/500 PDF pages and output to 2,000,000 characters. The child receives a private per-attempt directory and no network-dependent behavior. Unsupported platforms or inability to establish containment fail closed unless a separately reviewed equivalent isolation adapter is implemented.
- Extracted text, partial text, and staged results are document content. They use opaque server-generated storage keys under non-served private roots, path-containment/exclusive-creation controls, least-privilege access, integrity metadata, and attachment-equivalent backup/reconciliation rules.
- Every read of extracted text or staged content is service-mediated through the parent document's current authorization and visibility state. App Admin has no implicit access. Direct storage keys, old versions, and worker identifiers confer no authority.
- Staging content is attempt-scoped and is atomically promoted only after all publication fences pass. Failure, timeout, cancellation, or stale publication removes it or moves it to controlled quarantine without logging its contents or path.
- Extracted/staged content follows document archive, deletion, 30-day purge eligibility, backup, restore, reconciliation, and audit restrictions. Logs, audit events, exceptions, metrics, SSR, URLs, and browser storage must never contain extracted text or sensitive filenames.

## Proposed bounded implementation batches

One Product Owner authorization may cover all batches after ratification, but Codex must stop at each objective SOL G2 boundary and may continue only on PASS for the exact reviewed head.

| Batch | Tasks | Deliverable boundary | Required evidence before SOL G2 |
| --- | --- | --- | --- |
| A - Domain and authorization | IC-009, IC-010 | Models/migrations, lifecycle service, permission/query policy, audit vocabulary | Native MySQL migrations/drift; complete matrix tests; cross-owner/direct-ID denials; audit-failure rollback; no content leakage |
| B - Upload and storage | IC-011 | Validated upload, private artifact adapter, compensation and integrity metadata | Traversal/reparse containment; type/size/encryption rejection; CSRF; artifact/DB/audit failure matrix; orphan handling; no public serving |
| C - Jobs and worker | IC-012, IC-013 | Queue state machine, atomic worker, extraction/result publication | Native MySQL multi-worker races; leases/fencing; retry/idempotence/cancel; parser/resource failures; transaction rollback; log scans |
| D - API and UI | IC-014, IC-015 | DRF contracts and browser workflows | Authorization/CSRF/streaming contracts; frontend unit/type/lint/build; real Chrome; browser storage/console scans |
| E - Recovery and integration | IC-016, IC-017 | Operator recovery, complete regressions, living documents and closeout | Dry-run/execution/idempotence/failure recovery; full backend/frontend/browser/security suite; F-01/F-02 regression; scope/diff audit |

### Objective G2 review points

1. **Authorization G2 (Batch A):** PASS only if every actor/action matrix cell has positive or negative executable evidence, App Admin content denial is proven, query filtering and direct-object checks agree, deactivation is immediate, and required audit failure rolls back mutations.
2. **Storage/upload G2 (Batch B):** PASS only if the reviewed head proves path containment on Windows, private non-served storage, bounded format validation, CSRF, exclusive creation, digest/size integrity, and compensation across each artifact/database/audit/enqueue failure point.
3. **Worker concurrency G2 (Batch C):** PASS only if native MySQL races prove one claimant/accepted result, lease fencing and stale-worker rejection, bounded retries, cancellation/deletion races, idempotent recovery, parser limits, and secret-free logs.
4. **Final integration G2 (Batches D/E):** PASS only if the exact feature head passes full native-MySQL backend, complete frontend, production build, Chrome end-to-end, migration/drift, synthetic-secret, authorization, recovery, and F-01/F-02 regressions; task living documents and feature inventory must match the head.

Any failed security, migration, concurrency, rollback, or scope check stops consolidated execution. Fixes require a new exact review head; repository protections and separate feature-to-main authorization remain mandatory.

## Proposed verification minimum

- Native Windows MySQL for migrations, constraints, row-locking concurrency, rollback, idempotence, and the complete Django suite.
- Filesystem tests on the supported Windows local-MVP path, including traversal and reparse-point/symlink escape attempts.
- Complete frontend unit tests, TypeScript, ESLint, and production build.
- Real Chrome/Playwright upload, status, authorization, download, archive/restore/delete, retry, and deactivation scenarios.
- Synthetic document-content and filename markers scanned across database audit fields, server/worker/Next.js logs, SSR output, URLs, browser storage, and browser console.
- `npm run validate`, `git diff --check`, model-drift checks, task/feature documentation inventory, and exact-SHA evidence at each batch boundary.

## Ratification record

The Product Owner selected **RATIFIED WITH MANDATORY CLARIFICATIONS** at authorized proposal SHA `5016a7b50edcfc8d67824e13bbb647a116fdbe79`. This finalized baseline resolves the three SOL requirements without expanding product scope or weakening a security control:

1. document visibility and immutable-version processing are separate state machines with explicit archive, restore, delete, replacement, cancellation, and stale-publication behavior;
2. parser deadline and memory limits are enforced by a killable isolated child/process tree, not a post-return timer; and
3. extracted and staged text receive the same content authorization, App Admin isolation, private storage, retention, purge, backup, reconciliation, and logging protections as original artifacts.

Batch A (IC-009 and IC-010) is authorized. Work must stop for SOL G2 review at the exact Batch A head before Batch B begins.
