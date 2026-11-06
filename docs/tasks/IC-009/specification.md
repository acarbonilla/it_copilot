# IC-009 - Document Domain and Lifecycle

**Status:** Product Owner ratified under the F-03 consolidated G1 baseline
**Finalized G1 specification:** `054bb5427b898a2e46eb085892d0b3f58a71b54c`
**Dependencies:** IC-002, IC-003, and IC-008

## Objective

Establish the native-MySQL document aggregate, separate document visibility and version-processing state, immutable ownership, optimistic metadata revision, constraints, and atomic controlled audit contract used by later F-03 batches.

## Batch A scope

- `Document`, `DocumentVersion`, `ProcessingJob`, and `ExtractedTextArtifact` schema foundations.
- Document visibility states `ACTIVE`, `ARCHIVED`, and `DELETED`.
- Version processing states `STAGED`, `QUEUED`, `PROCESSING`, `READY`, `FAILED`, and `CANCELLED`.
- Immutable owner, current/candidate version references, monotonic metadata revision, safe title/description, timestamps, and deletion marker.
- Transactional create, metadata update, archive, restore, and soft-delete services using row locking and expected revision.
- Controlled non-content audit actions with fail-closed rollback.

Upload/storage, job execution, parser behavior, API endpoints, frontend behavior, and physical purge are excluded from Batch A and remain assigned to later ratified tasks.

## Acceptance criteria

1. Forward migrations create the four domain structures, indexes, foreign keys, uniqueness checks, state choices, positive-value checks, deletion consistency, one version sequence per document, and at most one nonterminal job slot per version.
2. Document visibility is independent from version/job state; archive/restore/delete transitions are explicit and invalid or stale transitions do not mutate state or audit data.
3. Ownership never changes through a lifecycle/metadata service. Metadata updates require the exact positive revision and increment it once.
4. Critical create/update/archive/restore/delete operations record only controlled actor ID, document UUID, action, target type, outcome, and timestamp in the same transaction.
5. Required audit failure rolls back the corresponding document mutation.
6. Native MySQL migration apply/check, model-drift, constraint, concurrency, and full regression tests pass.

The complete ratified lifecycle, replacement-version, cancellation, stale-publication, parser-isolation, and extracted-text rules remain authoritative in the consolidated G1 specification.
