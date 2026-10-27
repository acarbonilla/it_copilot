# Architecture overview

## Current state

The Django REST API and MySQL persistence foundation are operational. IC-003
adds the email-based custom user and centralized role/ownership policy layer.
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
job lifecycle is intentionally deferred. Session authentication, UI, document
and vault models, deployment, retrieval, and external AI integrations are not
implemented by IC-003.

## Evolution rule

Each later task must update this document when it changes deployed components, communication paths, or ownership boundaries. Planned features must not be described as operational.

