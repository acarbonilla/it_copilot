# IC-011 Review Record

**Review gate:** F-03 Batch B upload/storage SOL G2
**Status:** Submitted for independent review
**Exact review head:** The submitted `feature/documentation-management` full SHA reported in the handoff/PR

## Objective PASS conditions

- Server-side authentication, role authorization, CSRF, 12 MiB request, 10 MiB file, and 500-page PDF bounds are enforced.
- Only safe PDF/TXT/Markdown reaches private storage; active/encrypted/malformed/unsupported input is rejected generically.
- User-controlled filenames never determine filesystem paths.
- Configured storage cannot be public, traverse the root, or use symlink/junction/reparse paths.
- Integrity metadata and guarded document/version ownership are consistent.
- Artifact, database, enqueue, audit, commit, and cleanup failure paths leave no usable partial document.
- Native Windows junction, native MySQL, migration/drift, complete backend, CSRF, authorization, and regression evidence pass.

## Residual risks and later obligations

- `pypdf` preflight occurs in the bounded upload request process. Batch C must not reuse this path for extraction; extraction requires the ratified killable Job Object child, hard deadline, and memory limit.
- No external antivirus scanner is active in the local MVP. Strict allowlisting, non-execution, private storage, PDF active-content rejection, and safe later download headers are the compensating controls.
- Private-root filesystem ACL correctness is an operator/deployment responsibility; the application uses non-public placement, exclusive files, restrictive modes where supported, and rejects reparse paths.
- Quarantined or crash-orphan artifacts remain private and require the IC-016 dry-run-first reconciliation command before deletion.
- Download authorization, attachment headers, and browser handling remain IC-014/IC-015.

Batch C must not begin without SOL G2 PASS on this exact head.
