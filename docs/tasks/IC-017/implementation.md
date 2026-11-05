# IC-017 Implementation Record

> IC-026 follow-up: publication/quarantine serialization and tombstone fencing were added after the original G2 HOLD. The native MySQL concurrency suite passed 7 tests; IC-026 SOL G2 review remains pending, F-03 remains at G2 HOLD, and PR #22 is not authorized for merge. IC-026-R01 records additional remediation evidence separately.

- A disposable native-MySQL/production-Next.js/real-Chrome harness creates isolated owner and App Admin-only identities with an in-memory random password and a temporary strict private root.
- The workflow signs in, uploads TXT content, runs the real Windows-isolated worker, observes ready status, verifies attachment headers/body, proves App Admin metadata-only separation, and exercises archive, restore, and delete.
- Browser local/session storage, URL, console events, Django/Next.js logs, and worker output are scanned for a synthetic content marker and sensitive filename. Disposable users, documents, artifacts, servers, and logs are removed afterward.
- Dedicated 3101/8101 origins avoid interfering with pre-existing local services; frontend/API origin settings remain configurable with secure localhost defaults.
