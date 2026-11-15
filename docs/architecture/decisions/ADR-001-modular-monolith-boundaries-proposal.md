# ADR-001 — Modular Monolith and Feature/Domain Boundaries (Proposal)

## Record status

- **Status:** Proposed for SOL review; not accepted and not authorized for implementation
- **Project:** IT Support Copilot V1.0 MVP
- **Governance:** Tri-Team Development Method (TTDM)
- **Date:** 2026-10-28
- **Decision owner:** Product Owner after SOL review
- **Scope of this record:** Documentation only

This proposal does not authorize a branch, pull request, file move, new Django app, frontend feature directory, schema migration, dependency change, worker, RAG implementation, vault implementation, deployment work, or merge. Every migration slice described below requires its own approved TTDM task and exact-head review.

## 1. Context

The repository is already a monorepo with a Next.js application, a Django REST Framework application, native MySQL persistence, reserved worker and API-contract locations, and cross-service test/documentation boundaries. The implemented identity work demonstrates useful domain behavior, but frontend feature code currently shares one `components` directory and one `lib/api.ts`, while the `accounts` Django app owns identity models, invitations, activation, user lifecycle, policies, API views, session revocation, and deletion-review initiation.

The architecture must remain simple enough for the MVP while preventing later documentation, RAG, credential-vault, and job-processing work from turning shared folders or the identity app into implicit global owners. Microservices would add operational and transactional complexity without an approved MVP need.

## 2. Proposed decision

Adopt a **modular monolith**:

1. Keep one Next.js web application, one Django/DRF application, one native MySQL database, and the existing monorepo.
2. Organize the frontend by product feature, with route files as thin composition points and each feature exposing a small public interface.
3. Organize the backend as domain-oriented Django apps. Each app owns its models, migrations, services, policies, API adapters, and tests unless a separately approved cross-cutting component has an explicit contract.
4. Keep database transactions inside the Django application. A service that owns a security-critical mutation owns its transaction and fail-closed audit call.
5. Separate shared HTTP transport mechanics from feature API contracts. Do not turn a shared client into a second business layer.
6. Keep worker execution separate from domain rules: workers invoke public domain services rather than duplicating or importing private model workflows.
7. Treat the credential vault as a high-isolation domain inside the monolith, with narrower dependencies and stronger secrecy rules than ordinary application data.

“Independent domain boundary” means independent ownership and dependency direction inside one deployable Django application. It does not mean a separate service, database, repository, or deployment.

## 3. Verified current structure

The following paths were verified in the repository on 2026-10-28. “Reserved” means the path contains documentation only; it is not an operational component.

```text
apps/
├── api/
│   ├── config/                    # settings, root URLs, structured errors, WSGI
│   ├── accounts/                  # users, invitations, activation, lifecycle, policies
│   ├── session_auth/              # CSRF/login/logout/current-user API views
│   ├── security_audit/            # audit model, migrations, recording service
│   ├── health/                    # health API
│   ├── manage.py
│   └── requirements.txt
└── web/
    ├── app/                       # /, /login, /dashboard, /activate, /admin/users
    ├── components/                # auth, activation, dashboard, admin-user components
    │   └── ui/                    # Button, Card, Input primitives
    ├── lib/
    │   ├── api.ts                 # transport, CSRF state, auth and user-admin contracts
    │   └── utils.ts
    ├── e2e/
    └── test/

packages/
└── api-contract/README.md         # reserved; no generated/shared contract yet

workers/
└── document_processor/README.md   # reserved; no worker entrypoint or job lifecycle yet

tests/
└── e2e/README.md                  # cross-service test boundary documentation

docs/
├── architecture/
├── api/
├── features/
├── process/
└── tasks/
```

Current runtime facts that this proposal must preserve:

- Django uses DRF session authentication, Django database sessions, CSRF middleware, exact local CORS origins, structured JSON errors, and a custom `accounts.User`.
- Root routes are currently registered in `apps/api/config/urls.py`.
- `accounts` calls the central `security_audit` service for controlled, atomic audit records.
- Next.js route files import components from the shared `components` directory; feature calls share `apps/web/lib/api.ts`.
- `packages/api-contract` and `workers/document_processor` are placeholders, not implemented capabilities.

## 4. Proposed target map

This map is a direction for files that exist or become authorized. It must **not** be created eagerly. Names are illustrative until the owning TTDM task approves them.

```text
apps/
├── web/
│   ├── app/                              # stable App Router URLs; thin composition
│   ├── features/
│   │   ├── auth/                         # activation/login/session UI + feature API
│   │   │   ├── api/
│   │   │   ├── components/
│   │   │   ├── model/                    # feature-local types/state when needed
│   │   │   ├── tests/
│   │   │   └── index.ts                  # public interface
│   │   └── user-administration/          # list/invite/lifecycle UI + feature API
│   │       └── index.ts
│   ├── shared/
│   │   ├── api/                          # HTTP, CSRF, error decoding only
│   │   ├── ui/                           # product-neutral UI primitives
│   │   └── lib/                          # product-neutral utilities
│   └── test/
│
├── api/
│   ├── config/                           # composition root only
│   ├── accounts/                         # identity/account lifecycle domain
│   │   ├── api/                          # DRF adapters and URLs
│   │   ├── services/                     # transactional use cases
│   │   ├── policies/                     # authorization decisions
│   │   ├── models/ or models.py          # app-owned persistence
│   │   └── tests/
│   ├── session_auth/                     # authentication HTTP/session boundary
│   ├── security_audit/                   # cross-cutting append-only audit capability
│   └── health/
│
packages/
└── api-contract/                         # only after contract task approval

workers/
└── document_processor/                   # only after job/worker task approval
```

Future documentation, RAG, job, or vault domains are deliberately absent from the proposed tree. Their directories and Django apps should be created only when a task authorizes working behavior and ownership.

## 5. Frontend ownership and import rules

### Feature ownership

A frontend feature owns its user workflows, feature-specific components, feature API adapter, validation/presentation types, and tests. Route files in `app/` own URL composition and server/client boundaries, but not feature business workflows. `shared/ui` owns product-neutral visual primitives; `shared/api` owns transport mechanics; neither owns identity or lifecycle semantics.

### Public interfaces

Each feature exposes supported imports through its root `index.ts`. Consumers import from `@/features/<feature>`, not from another feature's internal `components`, `api`, `model`, or test paths. A feature may import:

- its own private modules;
- public interfaces of other features, only when the dependency is explicit and unavoidable;
- `shared/*` modules;
- framework and approved package dependencies.

`shared/*` must not import from `features/*`. Features must not import from `app/*`. Route files may import feature public interfaces and shared layout/UI. Any cross-feature import through a public `index.ts` interface requires an explicitly documented dependency. Prefer coordination in a route or composition layer rather than direct cross-feature coupling where practical. Circular feature dependencies are prohibited; coordination belongs in a route/composition component or a newly approved shared contract.

Feature API adapters may expose typed functions such as `listUsers` or `activateAccount`, but components outside the owning feature should not construct its URLs or response shapes. Tests may reach private modules only when testing that feature; cross-feature tests use public interfaces.

### Incremental application to current files

- `components/login-form.tsx`, `activation-form.tsx`, and `auth-redirect.tsx` are candidates for an authorized `auth` slice.
- `components/admin-users.tsx` is a candidate for an authorized `user-administration` slice.
- `components/ui/*` and `lib/utils.ts` are candidates for `shared/ui` and `shared/lib`.
- `lib/api.ts` should be split only under a regression-backed task: shared request/CSRF/error transport plus auth and administration feature adapters.
- `app/*/page.tsx` paths and observable route behavior remain unchanged.

No move is proposed merely to make the tree look complete.

## 6. Backend domain rules

### Ownership

A Django domain app owns its database tables and migration history, domain services, authorization policies, API serializers/adapters, URL module, signals required to preserve its invariants, and tests. Other apps do not write its models directly. Read access across domains should use a documented query/service interface or immutable identifier/value object, not an unrestricted model import.

Existing ownership remains:

- `accounts`: user identity, invitation/activation, lifecycle, App Admin membership, deletion-review initiation, and associated invariants.
- `session_auth`: HTTP authentication/session endpoints; it depends on Django auth and the accounts identity contract.
- `security_audit`: controlled audit vocabulary and persistence service. It does not own business mutations.
- `health`: operational health response only.
- `config`: composition root, settings, global error adaptation, and top-level URL inclusion; it owns no domain behavior.

### Service layer

DRF views validate HTTP shape, authenticate, invoke policy/service operations, and map stable outcomes to the existing error envelope. They do not implement multi-model workflows. Domain services accept explicit actor/target identifiers and validated command data; they do not accept raw requests, cookies, headers, or unrestricted payload dictionaries.

Services that modify state own:

1. invariant checks;
2. lock acquisition in a documented global order;
3. `transaction.atomic()` scope;
4. model writes;
5. required session or related-state changes;
6. fail-closed critical audit persistence.

Callers must not wrap a service in a transaction to change its atomicity contract without an approved design. Cross-domain mutations require one explicitly designated transaction owner and public service calls that are safe in that transaction; distributed transactions are not introduced.

### Permissions

Authorization remains server-side and deny-by-default. Policies are named functions or policy objects with explicit subject/resource inputs, separate from serializers and UI visibility. Django `is_staff`/`is_superuser`, App Admin, IT roles, ownership, authentication, and active state remain distinct concepts. UI hiding is usability only.

Negative matrices must cover anonymous, inactive, unknown-role, wrong-owner, role-only, staff/superuser-only, and App Admin cases as applicable. A domain may depend on the narrow account-policy contract; it must not copy role logic.

### Audit

Business domains choose the controlled action and nonsecret actor/target identifiers; `security_audit` validates and persists the allowlisted event. Successful security-critical mutation and audit event share the same transaction and fail closed. Denied events remain bounded best effort outside rollback-prone transactions. No domain may add secrets, emails, request bodies, IP addresses, session identifiers, cookies, tokens/digests, exception text, or free-form metadata to audit storage or logs.

Audit vocabulary expansion requires a forward migration and an owning task. Audit viewing, retention, and purge remain separate decisions.

## 7. HTTP transport and API contracts

### Shared transport

The proposed shared frontend transport owns only:

- API base URL resolution;
- `credentials: "include"`;
- JSON request/response handling;
- the structured `ApiError` envelope;
- CSRF bootstrap, rotation, and one bounded retry for `csrf_failed`;
- generic network failure normalization.

It must not know user roles, lifecycle states, invitation semantics, document types, vault data, or feature routes. It must not store passwords, activation tokens, CSRF tokens, cookies, or session identifiers in browser storage or logs.

### Feature contracts

Feature adapters own endpoint paths, request DTOs, response DTOs, pagination shapes, and mapping from wire data to feature types. Server contracts remain authoritative in DRF. Until a separate contract task is approved, TypeScript types are maintained alongside the consuming feature and verified by tests.

`packages/api-contract` remains reserved. A later task may propose an OpenAPI document or generated types, but this ADR does not select a generator, introduce code generation, change compatibility policy, or add a dependency. Any such task must define source of truth, generation/check commands, reviewable diffs, backward-compatibility rules, and CI enforcement.

API version `/api/v1`, existing route paths, session/CSRF behavior, status codes, and error envelopes are migration invariants.

## 8. Worker, job, and RAG boundaries

The reserved `workers/document_processor` boundary may later host an independently runnable Django-managed process. A worker should receive opaque job identifiers, claim work using an approved database-backed lifecycle, and invoke public domain services. It must not import DRF views, duplicate authorization rules, bypass domain transactions/audit, or make direct cross-domain table updates.

The following choices are **deferred and unapproved**:

- job schema, state machine, retry/backoff, leases, idempotency keys, scheduling, cancellation, and dead-letter handling;
- worker command/process manager and concurrency model;
- document parsing, chunking, embedding model/provider, prompt design, retrieval ranking, citations, and evaluation thresholds;
- vector storage technology, including whether MySQL is sufficient or any vector database is needed;
- external AI provider, hosted services, network egress, telemetry, and production deployment.

RAG should be treated as application/domain behavior behind explicit ingestion and retrieval interfaces. Source-document authorization must be checked before ingestion and again before retrieval results are exposed. Derived chunks, embeddings, indexes, and caches inherit source sensitivity and deletion/retention obligations. No new vector database is implied by this proposal.

## 9. Vault security-isolation principles

The future credential vault is a high-risk bounded domain, not a shared utility. Until its separately approved threat model and cryptographic design exist:

- no vault Django app, model, endpoint, frontend feature, worker, or placeholder secret field should be created;
- vault plaintext must never enter audit events, logs, URLs, analytics, RAG corpora, prompts, generic search, browser storage, or error responses;
- authorization must be ownership-based and server-side, with App Admin, staff, superuser, or IT roles granting no implicit secret access;
- secret access and secret metadata access should be separate capabilities;
- encryption format, key hierarchy, key storage, rotation, recovery, export, clipboard behavior, reauthentication, masking, retention, and deletion are deferred to a security-reviewed task;
- shared HTTP and UI layers must remain unaware of plaintext secret values beyond the minimum typed boundary required by an approved vault workflow;
- vault tables and services must not be directly imported by document/RAG or general administration domains.

This ADR does not approve application-managed encryption or claim that database/storage encryption alone is sufficient.

## 10. Incremental migration plan

Each stage is independently reviewable and must preserve routes, behavior, schema, security controls, and deployment topology.

**Prerequisite:** Architecture implementation and identity/administration file moves must not begin until IC-007 completes SOL G2/G3 review and receives separate Product Owner merge authorization.

### Stage 0 — Baseline and dependency rules

Create a separately authorized architecture-baseline task to accept or revise this ADR, record dependency rules, inventory public interfaces, and establish import checks using existing tooling where possible. No code moves. Required evidence: current backend/frontend/full regression and clean model drift.

### Stage 1 — Frontend shared transport extraction

Under a frontend-only task, characterize `lib/api.ts`, then extract transport/CSRF/error mechanics without changing feature functions or wire behavior. Keep compatibility re-exports temporarily if needed. Required regressions: auth, CSRF rotation/retry, network errors, activation secrecy, admin mutations, TypeScript, lint, tests, and production build.

### Stage 2 — Frontend feature slices

Move one implemented workflow at a time, beginning with the smallest cohesive feature. Route paths stay fixed. Add a public `index.ts`, migrate imports, run feature and full frontend regressions, then remove compatibility exports only after consumers are migrated. Do not create directories for unimplemented features.

### Stage 3 — Django API composition and service packaging

For one existing app at a time, introduce app-owned `urls.py` and, only where volume justifies it, `api/`, `services/`, or `policies/` packages. Preserve migration modules and model import identity. Root `config/urls.py` becomes composition through `include()` without route changes. Each move requires native MySQL tests, migration graph/model-drift checks, authorization matrices, CSRF/session regressions, and audit failure injection.

### Stage 4 — New business domains when authorized

Create a Django app or frontend feature only with its first approved vertical slice. Its task must name ownership, public interfaces, dependency direction, schema, permissions, transaction owner, audit events, privacy classification, and deletion/retention behavior. This stage does not pre-authorize documentation, RAG, jobs, or vault work.

### Stage 5 — Worker/job boundary

After a job lifecycle decision is approved, implement the smallest independently runnable worker path using domain public services. Prove claim/lease concurrency, idempotency, retry limits, audit behavior, shutdown recovery, and parity with synchronous authorization. Do not add hosted infrastructure under this architecture record.

### Stage 6 — Contract automation, if justified

Only after API breadth makes duplication materially risky, evaluate a contract source and validation/generation workflow for `packages/api-contract`. Adoption requires a separate ADR/task and may not silently add dependencies.

## 11. Migration risks and controls

| Risk | Required control |
| --- | --- |
| Import-only refactor changes client/server boundaries | Production Next.js build plus route rendering and hydration tests |
| CSRF/session regression during transport split | Existing login/logout/activation/admin CSRF suites and cookie-session tests |
| Route or error-envelope drift | Route inventory and exact response-contract tests before and after each slice |
| Django model identity or migration drift | Never move migrations casually; run migration graph, `makemigrations --check`, and native MySQL migrate tests |
| Transaction boundary split across services | One declared transaction owner; audit and failure-injection tests |
| Circular domain/feature dependencies | Public-interface imports, dependency review, and a composition-layer fix rather than reciprocal imports |
| “Shared” becomes a dumping ground | Shared modules must be domain-neutral and have multiple real consumers or a clear platform role |
| Premature directories imply approved scope | Create boundaries only with authorized, working feature slices |
| Worker bypasses authorization/audit | Worker invokes the same public domain services and runs parity tests |
| Vault or RAG leaks secrets | Explicit information classification, negative serialization/logging tests, and separate security review |
| Large moves obscure security changes | Small mechanical commits/tasks; no behavior change mixed with relocation unless explicitly approved |

## 12. Regression and TTDM gates

Every implementation task derived from this proposal must document:

- exact authorized scope and exclusions;
- before/after path map and public interfaces;
- route, response, schema, migration, authorization, session, CSRF, audit, and secrecy invariants;
- focused tests plus complete affected backend/frontend regressions;
- native MySQL evidence for database or concurrency-sensitive changes;
- TypeScript, ESLint, frontend tests, production build, Django checks, model drift, repository validation, and `git diff --check` as applicable;
- failures corrected, limitations, exact commit SHA, and rollback approach;
- SOL review and separate Product Owner approval before merge.

Suggested task boundaries are: architecture-rule acceptance; shared frontend transport; auth feature slice; user-administration feature slice; Django URL composition; accounts service packaging; and only later separately approved domain/worker/contract tasks. Combining all moves into one repository-wide refactor is not proposed.

## 13. Consequences

### Expected benefits

- Domain and feature ownership becomes discoverable without adding deployment units.
- Security-critical transactions, permissions, and audit behavior remain close to owning use cases.
- Frontend features can evolve without a global API/component module becoming the de facto architecture.
- Later workers reuse domain behavior without importing HTTP adapters.
- High-risk vault and RAG concerns receive explicit isolation rather than accidental shared access.

### Costs and tradeoffs

- More explicit public interfaces and some indirection.
- Temporary compatibility exports during incremental moves.
- Continued single-database coupling, intentionally accepted for MVP atomicity and operational simplicity.
- Boundary discipline relies on review and tests until a separately approved enforcement mechanism exists.

## 14. Alternatives considered

- **Keep purely layer-based/global folders:** lowest immediate effort, but ownership and dependency direction degrade as features grow.
- **Repository-wide “big bang” reorganization:** visually fast but high regression risk and poor reviewability; rejected.
- **Microservices or separate databases:** unnecessary operational, security, and consistency burden for the MVP; rejected by constraint.
- **Create all future domains now:** produces empty speculative structure and falsely implies authorization; rejected.

## 15. Approval boundary

SOL may recommend acceptance, revision, or rejection. Product Owner approval is required before this becomes an accepted ADR or generates any migration task. Acceptance of the architectural direction would still not authorize a code move, schema change, dependency addition, worker, RAG system, vault, deployment, branch, PR, or merge.
