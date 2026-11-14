# Architecture overview

## Current state

The Django REST API and MySQL persistence foundation are operational. IC-003
adds the email-based custom user and centralized role/ownership policy layer.
IC-004 adds database-backed browser sessions with CSRF-protected login/logout,
current-user lookup, exact-origin local CORS, and immediate deactivation denial.
The planned system separates a future Next.js web process, the Django REST API,
a Django-managed document-processing worker, and MySQL. API contract artifacts
and cross-service end-to-end tests have dedicated locations.

```text
apps/web  ->  apps/api  ->  MySQL
                 |
                 +---- shared Django business logic ---- workers/document_processor

packages/api-contract: API schema/client boundary
tests/e2e: cross-service verification boundary
```

The worker must have an independently runnable entrypoint. Its database-backed
job lifecycle is intentionally deferred. Login UI, account lifecycle/bulk
session cleanup, document and vault models, deployment, retrieval, and external
AI integrations remain deferred.

## Evolution rule

Each later task must update this document when it changes deployed components, communication paths, or ownership boundaries. Planned features must not be described as operational.

## IC-021 vault boundary

The Django API now owns a vault domain and narrow cryptographic service. A
service-controlled external KEK wraps per-owner DEKs; those DEKs encrypt record
payloads with AES-256-GCM. MySQL stores metadata, versioned envelopes, wrapped
DEKs, lifecycle, and append-only controlled audits, but never KEK or plaintext.
The API process has access to both the external KEK and database and therefore
remains a shared-process residual risk; module separation is not OS isolation.

Metadata reads are active-session and owner scoped. All sensitive production
routes remain fail closed until IC-022 supplies accepted reauthentication and
single-use grants. Document workers, Copilot, Next.js, administrators, and IT
roles receive no vault key or reveal capability.

