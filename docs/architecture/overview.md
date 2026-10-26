# Architecture overview

## Current state

IC-001 establishes boundaries but no application runtime. The planned system separates a Next.js web process, a Django REST API, a Django-managed document-processing worker, and MySQL. API contract artifacts and cross-service end-to-end tests have dedicated locations.

```text
apps/web  ->  apps/api  ->  MySQL
                 |
                 +---- shared Django business logic ---- workers/document_processor

packages/api-contract: API schema/client boundary
tests/e2e: cross-service verification boundary
```

The worker must have an independently runnable entrypoint. Its database-backed job lifecycle is intentionally deferred. Deployment topology, authentication, credential security, retrieval, and external AI integrations are not decided or implemented here.

## Evolution rule

Each later task must update this document when it changes deployed components, communication paths, or ownership boundaries. Planned features must not be described as operational.

