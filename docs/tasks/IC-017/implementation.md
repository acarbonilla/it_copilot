# IC-017 Implementation Record

- A disposable native-MySQL/production-Next.js/real-Chrome harness creates isolated owner and App Admin-only identities with an in-memory random password and a temporary strict private root.
- The workflow signs in, uploads TXT content, runs the real Windows-isolated worker, observes ready status, verifies attachment headers/body, proves App Admin metadata-only separation, and exercises archive, restore, and delete.
- Browser local/session storage, URL, console events, Django/Next.js logs, and worker output are scanned for a synthetic content marker and sensitive filename. Disposable users, documents, artifacts, servers, and logs are removed afterward.
- Dedicated 3101/8101 origins avoid interfering with pre-existing local services; frontend/API origin settings remain configurable with secure localhost defaults.
