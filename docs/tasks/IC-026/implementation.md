# IC-026 Implementation Record

- Added the singleton `ArtifactPublicationGuard` row and `lock_artifact_publication()` coordination boundary.
- Added `QuarantinedArtifact` tombstones so quarantine winning a race permanently fences late publication of that storage key.
- Original upload and extracted-text publication acquire the guard before creating an artifact reference and reject a tombstoned key.
- Orphan execution acquires the guard, revalidates `OriginalArtifact` and `ExtractedTextArtifact`, then moves, tombstones, and critically audits the artifact.
- Critical-audit/tombstone failure restores the file before the guard is released; restore failure remains an exception and late publishers remain fail-closed.
- Repeated execution returns `already_reconciled`; a newly referenced candidate returns `referenced` without storage mutation or audit success.

Files outside IC-026 were not refactored. No merge was performed.
