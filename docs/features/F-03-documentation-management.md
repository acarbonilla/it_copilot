# F-03 — Documentation Management

**Status:** Consolidated G1 ratified with mandatory clarifications; Batch A authorized
**Branch:** `feature/documentation-management`
**Verified planning baseline:** `b3adb37a6ac029053b4215ba08067de1427ab993`
**Product Owner authorization:** Planning, investigation, feature-branch preparation, and task specification only
**SOL planning review:** PASS, review `5693729644`

The single ratifiable proposal is [F-03 Consolidated G1 Requirements Proposal](F-03-consolidated-g1-proposal.md). Every task definition and decision there is explicitly proposed rather than represented as an existing authoritative requirement.

The Product Owner ratified the proposal at `5016a7b50edcfc8d67824e13bbb647a116fdbe79`, including Batches A-E subject to exact-head SOL G2 PASS at the four defined boundaries. SOL G1 review is `5693795827`. The finalized baseline separates document visibility from version processing, requires enforceable Windows parser process isolation/deadlines/resource limits, and protects extracted/staged text as document content. The exact finalization commit is recorded below after creation.

**Finalized G1 specification commit:** `054bb5427b898a2e46eb085892d0b3f58a71b54c`

## Scope and source status

The repository assigns IC-009 through IC-017 to F-03 and identifies document management plus asynchronous document processing as planned MVP capabilities. It does not define the individual task titles, objectives, implementation scopes, acceptance criteria, verification requirements, or task dependencies for IC-009 through IC-017.

Discovery checked:

- `docs/product/mvp-requirements.md`, architecture overview/data model, task and feature registries, and TTDM-WA-001;
- all repository Markdown references to IC-009–IC-017 and F-03;
- GitHub issues and pull requests, open and closed, for each task code; and
- remote branch names containing those task codes or documentation-management terms.

No authoritative task definitions were found. This record therefore does not assign invented requirements to task codes. Product Owner-provided source definitions or explicit ratification of a proposed task breakdown is a hard prerequisite to implementation authorization.

## Known feature boundary

Authoritative repository statements establish only the following:

- F-03 groups IC-009–IC-017 on `feature/documentation-management`.
- The MVP plans document management and asynchronous document processing.
- The worker is Django-managed, independently runnable, and uses a database-backed job queue.
- The system direction is Next.js/TypeScript → Django/DRF → MySQL, with shared Django business logic used by the worker.
- IC-003 role/ownership policy exists but explicitly requires later document service/query paths to enforce it.
- Detailed behavior and acceptance criteria require later approved task specifications.

Excluded until separately specified: F-04 Copilot/retrieval behavior, external AI services, F-05 credential vault data, IC-024 permanent account deletion, production deployment, external storage/queue activation, and destructive data migration.

## Task inventory and requirements gap

| Task | Authoritative title | Authoritative objective/acceptance | Planning disposition |
| --- | --- | --- | --- |
| IC-009 | Not present | Not present | Blocked pending source definition |
| IC-010 | Not present | Not present | Blocked pending source definition |
| IC-011 | Not present | Not present | Blocked pending source definition |
| IC-012 | Not present | Not present | Blocked pending source definition |
| IC-013 | Not present | Not present | Blocked pending source definition |
| IC-014 | Not present | Not present | Blocked pending source definition |
| IC-015 | Not present | Not present | Blocked pending source definition |
| IC-016 | Not present | Not present | Blocked pending source definition |
| IC-017 | Not present | Not present | Blocked pending source definition |

Until the consolidated proposal is ratified or replacement definitions are supplied, task specifications and four-document task folders must not claim G1 approval.

## Dependency graph

```text
F-01 authentication/session/CSRF
  ├─ authenticated document API and UI
  └─ ownership and IT-role policy foundations

F-02 identity/lifecycle/audit
  ├─ active-account enforcement and App Admin separation
  ├─ immutable actor attribution and authorization-denial audit
  └─ deactivation/session behavior during document operations

Ratified F-03 domain and authorization contract
  ├─ persistence and migrations
  ├─ upload/storage boundary
  ├─ database-backed processing jobs → independently runnable worker
  ├─ document management API → Next.js management UI
  └─ recovery/integration evidence

Future F-04 retrieval/Copilot may consume accepted processed-document outputs;
F-03 must not implement F-04 behavior implicitly.
```

## Proposed implementation sequence — conditional, not task mapping

The following workstreams are a review proposal only. They cannot be assigned to IC-009–IC-017 until the Product Owner ratifies the authoritative task breakdown.

| Batch | Proposed workstream | Safe consolidation | Required SOL boundary |
| --- | --- | --- | --- |
| 0 | Requirements ratification | Resolve all task titles, lifecycle, permission, storage, and processing decisions together | Product Owner G0/G1 before code |
| A | Domain, lifecycle, authorization, and audit contract | Schema plus service/query policy can be designed together because every later path depends on it | Review before migrations or endpoint implementation |
| B | Upload and durable storage | Upload validation, artifact creation, metadata persistence, compensation, and download boundary belong in one atomicity review | Review file/path/content and rollback threats |
| C | Database job queue and worker | Job state machine, claiming/lease protocol, retries, idempotency, parser limits, and failure recovery must ship as one concurrency boundary | Native MySQL concurrency/failure review |
| D | Document CRUD/list API and management UI | Backend contracts and corresponding Next.js screens may be delivered together once A–C are stable | Authorization/CSRF/browser review |
| E | Integrated recovery and closeout | Cross-service scenario, migrations, rollback, audit, performance limits, and recovery checkpoint | SOL integration review |

Parallel development is safe only after Batch A freezes identifiers, lifecycle states, permission rules, and audit vocabulary. Upload/storage and UI scaffolding may then proceed in parallel with worker internals, but integration must wait for the durable job contract.

## Proposed first implementation batch acceptance envelope

This is a candidate G1 envelope for Product Owner resolution, not an approved IC task specification:

1. Define the document aggregate, immutable identifiers, ownership/visibility fields, lifecycle states, timestamps, versioning/concurrency rule, and deletion semantics.
2. Publish a deny-by-default permission matrix for App Admin, `IT_DOC_ADMIN`, `IT_EDITOR`, `IT_MEMBER`, owner, non-owner, inactive user, and anonymous user across list/read/create/update/upload/process/delete actions.
3. Decide which operations produce critical atomic audit events and extend the controlled vocabulary through forward migrations without secret or document-content fields.
4. Define MySQL constraints/indexes, forward-only migration dependencies, rollback/recovery expectations, and model-drift checks.
5. Define bounded DRF request/response/error contracts without exposing storage paths, parser diagnostics, private document content, or unrestricted metadata.
6. Require service/query-layer authorization tests, cross-owner negative tests, CSRF tests, audit-failure rollback tests, and native MySQL concurrency tests before later batches consume the domain.
7. Update architecture/data-model documents only after the design is approved and implemented; planned components must not be described as operational.

No code or migration should be created from this envelope until the missing task definitions and decisions below are approved.

## Required design decisions

Product Owner/SOL resolution is required for:

1. Exact IC-009–IC-017 titles, objectives, acceptance criteria, and dependencies.
2. Document ownership model: personal, shared, organization-wide, or a combination.
3. Exact capability matrix for each IT role and App Admin; whether App Admin has document-content access.
4. Document lifecycle and deletion/archive/restore semantics; retention and relationship to deferred IC-024.
5. Accepted upload types, maximum request/file/page sizes, batch behavior, duplicate policy, and filename treatment.
6. Durable binary storage for the local MVP: database, contained filesystem, or another explicitly approved adapter.
7. Malware/scanning expectation, parser/library choices, archive handling, macro handling, and encrypted/password-protected files.
8. Processing outputs: extracted text, metadata, chunks, status, diagnostics, and what future F-04 may consume.
9. Job states, priority, attempts, leases/timeouts, retry/backoff, cancellation, poison-job handling, and operator recovery.
10. Versioning and concurrent edit/upload behavior, including optimistic-lock or last-write policy.
11. Search/list/filter/sort/pagination requirements and whether content search belongs to F-03 or F-04.
12. Audit event vocabulary and whether filenames/titles are permitted audit data (default recommendation: no free text).
13. Download/preview requirements and browser security headers.
14. Local storage cleanup/reconciliation behavior after database, artifact, parser, or process failure.
15. Performance/volume targets needed to bound synchronous API work and worker throughput tests.

## Security and data-integrity boundaries

| Boundary | Required control before implementation acceptance |
| --- | --- |
| Authorization | Server-side object/query filtering; deny by default; never trust frontend-hidden controls; inactive users denied on every request |
| Upload | Bounded body/file count/size; extension plus content validation; filename neutralization; path containment; exclusive/non-overwriting creation; CSRF |
| Content handling | Treat all uploaded content as hostile; no executable macros; parser time/memory/page limits; archive-bomb and recursive-container policy |
| Storage | Opaque IDs; no user-controlled paths; least-privilege directory/account; private-by-default access; no path/secret leakage |
| Processing queue | Transactional enqueue; atomic claim; lease/heartbeat decision; bounded retries; idempotent completion; stale-job recovery; no double publication |
| Worker isolation | Independently runnable entrypoint; same authorization-independent service rules; no inbound public endpoint; sanitized logs/errors |
| Database integrity | Forward migrations, FK/check/unique constraints, deterministic lock order, race tests, and audit/state atomicity |
| Observability/audit | Controlled nonsecret identifiers only; no raw content, filename, storage path, exception, cookie, token, or unrestricted parser output |
| Browser/download | Authorization on every fetch; safe content disposition/type; no inline execution of hostile formats; no secret browser storage |
| Deletion/recovery | Explicit lifecycle; reference-aware cleanup; compensating artifact handling; reconciliation procedure; no IC-024 expansion |

## Anticipated artifacts after requirements approval

- Django domain app/models and forward migrations.
- Controlled audit vocabulary migration if required.
- DRF endpoints and API contract documentation.
- Next.js document list/detail/upload/status screens.
- Django management-command worker entrypoint and database-backed job services.
- Native MySQL concurrency, migration, authorization, audit, rollback, idempotence, and artifact-failure suites.
- Frontend unit, TypeScript, lint, build, and real-browser upload/processing scenarios.
- Four living documents for each authorized task: `specification.md`, `implementation.md`, `test-results.md`, and `review.md`.

## Recovery checkpoints

| Purpose | Backup branch | Verified full SHA | Checks | Created | Cleanup approval |
| --- | --- | --- | --- | --- | --- |
| Planning baseline | Pending authorization | `b3adb37a6ac029053b4215ba08067de1427ab993` | Remote/local main equality | 2026-10-29 | Pending |
| Before first schema integration | Pending | Pending | Native migrations, drift, focused/full regressions | Pending | Pending |
| Before feature release | Pending | Pending | Full backend/frontend/browser/security evidence | Pending | Pending |

## Express delivery governance

- Consolidated implementation authorization may cover multiple ratified tasks/batches, but each task retains explicit acceptance criteria and four living documents.
- SOL review occurs at the domain/authorization contract, upload/storage boundary, worker concurrency boundary, and final integration boundary rather than at arbitrary administrative intervals.
- A batch must stop on schema/permission ambiguity, unsafe artifact handling, concurrency failure, model drift, or a missing external dependency.
- Task PRs target this feature branch; no F-03 merge to `main` is authorized by planning approval.
- The feature record will capture exact task heads, integration commits, test evidence, and recovery refs as implementation proceeds.

## Planning recommendation

**HOLD implementation; READY for consolidated SOL/Product Owner G1 review.** The repository did not contain authoritative task definitions. The linked package now proposes a complete mapping and decision sheet without presenting it as pre-existing authority. Ratification and consolidated implementation authorization remain required before code.
