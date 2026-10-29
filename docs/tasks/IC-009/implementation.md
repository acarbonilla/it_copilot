# IC-009 Implementation Record

**Batch:** F-03 Batch A
**Implementation commit:** `494973c3ed493ce4b484dd819f41a3c9fa4f5277`

## Implementation

- Added the `documents` Django app and registered it in shared settings.
- Added UUID `Document`, `DocumentVersion`, `ProcessingJob`, and `ExtractedTextArtifact` models.
- Kept document visibility independent from immutable-version processing and job state.
- Added database constraints/indexes for revisions, deletion timestamps, version sequences, actor snapshots, extracted-text bounds, job attempts, state/slot consistency, and one nonterminal job slot.
- Added transactional lifecycle services. Document rows are locked before mutation and optimistic `metadata_revision` rejects stale writes.
- Added audit vocabulary for document create, metadata update, archive, restore, and deletion. Critical audit writes share the mutation transaction.

No upload, artifact I/O, parser, worker, public API, UI, purge command, or F-04 behavior was introduced.

## Migrations

- `documents/0001_initial.py`
- `documents/0002_processingjob_processing_job_slot_matches_state.py`
- `security_audit/0005_remove_securityauditevent_audit_action_known_and_more.py`

The generated audit migration name reflects Django's automatic constraint replacement; it adds the five controlled document actions while preserving all prior vocabulary.
