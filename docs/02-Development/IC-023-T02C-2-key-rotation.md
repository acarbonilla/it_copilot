# IC-023-T02C-2 — Controlled KEK/DEK rotation

**Task:** IC-023-T02C-2-T01
**Baseline:** `a1cfeaff89b6768569fbf0fbe53400e22d3797a0`
**Branch:** `feature/ic-023-key-rotation`
**Risk:** L3 — security-critical
**PO authorization:** APPROVED FOR LOCAL ENGINEERING IMPLEMENTATION
**PO acceptance:** PASS WITH ACCEPTED LIMITATIONS
**Git publication:** AUTHORIZED BY IC-023-T02C-2-GIT-01; PR MERGE NOT AUTHORIZED
**Operational key operations:** PROHIBITED
**Operational destructive purge:** MANDATORY HOLD

## Scope and generation model

R01–R10 are implemented as an inactive local foundation. `VaultRecord.key_version` remains the per-owner DEK generation. `VaultOwnerKey.kek_generation` independently records which external KEK generation wraps that DEK. Migration 0007 assigns existing rows to explicit legacy KEK generation 1; it never reinterprets record key versions.

The versioned provider is an external protected JSON file containing an explicit active generation and unique positive generation entries with base64-encoded 256-bit keys. Unknown versions, duplicate versions, malformed keys, provider files inside the repository, and ambiguous legacy/provider configuration fail closed. Legacy `VAULT_KEK_BASE64` or `VAULT_KEK_FILE` remains generation 1 only. Activation is an external custody action and is not performed by application code.

## R01–R10 implementation

- **R01:** separate KEK and DEK generation columns and contracts.
- **R02:** exact-generation external retrieval with strict 256-bit validation and no historical fallback.
- **R03:** disposable-only authenticated DEK rewrap preserves DEK bytes, record ciphertext, and record DEK generation; new wrapping nonces and verification precede publication.
- **R04:** disposable-only owner DEK replacement decrypts and authenticates every ACTIVE/DELETED envelope, creates a monotonic DEK generation, re-encrypts with fresh nonces, increments revisions, and never selects PURGED material.
- **R05:** read-only retirement assessment returns nonsecret reason codes; there is no delete, command, API, scheduler, or worker.
- **R06:** global guard, owner/key/record ordering, row locks, candidate/revision digest revalidation, atomic transactions, one-use confirmation, replay denial, and unique active-slot enforcement protect publication.
- **R07:** historical KEK lookup is explicit; active backup creation blocks rotation, retained backup uncertainty blocks retirement, and missing recovery evidence denies retirement.
- **R08:** existing protected maintenance principals and `key.rotate.kek`, `key.rotate.dek`, and `key.retire.online` capabilities are used. Confirmation issuer and executor must differ; trusted time, expiry, digest, and replay checks are enforced.
- **R09:** public execute functions unconditionally raise `OperationalRotationDisabled`. Actual mutation helpers are private and additionally require a Django disposable test database. No route, frontend, management command, worker, or environment Boolean enables them.
- **R10:** transformations are verified before save and transactions roll back cryptographic or publication failures. Pending operation/journal state remains available for reconciliation after interruption.

## Workflows and lock ordering

KEK assessment binds source generation, active target generation, and a bounded ordered owner-key set. Execution locks the global guard, operation/confirmation/journal, owners, then owner-key rows. Each DEK is authenticated with its recorded source KEK, rewrapped with the target KEK using fresh AES-GCM material, verified by unwrap, and only then stored.

DEK assessment binds owner, record IDs, revisions, lifecycle states, and old DEK generations. Execution locks the global guard, operation/confirmation/journal, owner, all owner-key generations, then non-PURGED records ordered by UUID. It authenticates all source envelopes before writes, retires only the prior active slot, creates one fresh active DEK generation, re-encrypts ACTIVE and DELETED records, verifies plaintext equivalence, and increments every affected revision atomically. Batch size is capped at 100; larger sets require future approved checkpoint orchestration.

CRUD locks owners and owner keys before credential mutation. Rotation uses the same hierarchy. Active holds, unfinished owner/purge journals, or in-progress backup artifacts deny execution. The native duplicate-execution test verifies MySQL serialization and active-key uniqueness. Rotation-versus-update/delete/restore/purge/snapshot interleaving is protected by shared locks and fail-closed conflict checks but has not received a separate native test for every pair.

## Retirement rules

The evaluator denies active keys, record references including restorable DELETED records, active holds, unfinished owner or purge-scope journals, retained/unknown backup dependencies, unavailable current recovery evidence, and missing historical KEKs. Unknown inventory is not eligible. No key deletion mechanism exists.

## Verification evidence

- Focused rotation/crypto/key/service/lifecycle/purge/backup suite: `63` run, `61` passed, `2` skipped (native-only tests). After protected-provider hardening, the directly affected rotation/key/service subset ran `32`, passed `31`, and skipped `1` native-only test.
- Full vault regression before the final disposable-database identity refinement: `115` run, `101` passed, `14` skipped. The refinement affects only the private execution boundary; its exact final source was rerun with `6` SQLite rotation tests and `1` native MySQL concurrency test, all passing.
- Native MySQL duplicate DEK rotation: `1` run, `1` passed on disposable `test_my_database`; exactly one completion, one denial, and one active owner key.
- Django system check: no issues.
- Migration drift: none.
- Migration 0007: complete-schema forward, reverse to 0006, and forward to 0007 passed on a disposable SQLite database, which was removed.
- `git diff --check`: passed at completion.

Positive cryptographic tests use only disposable users, credentials, databases, provider files, and test keys. They demonstrate identical DEK after KEK rewrap, fresh wrapping material, unchanged credential ciphertext during KEK rotation, fresh DEK generation and nonces during DEK rotation, ACTIVE/DELETED plaintext equivalence, rollback without mixed state, authorization/confirmation denial paths, and retirement denial reasons. Earlier T02C-3 evidence is reused only for unchanged backup/purge contracts.

## Outstanding limitations

- **L01:** Durable automatic resume/reconciliation orchestration is not implemented; interrupted operations remain pending and fail closed.
- **L02:** Per-pair native tests for rotation versus update, delete/restore, purge preparation, and active snapshot activity remain outstanding; shared ordering and denial rules are implemented.
- **L03:** External operational provider custody, ACL/SID deployment, activation, and escrow are deferred and not authorized.
- **P2-01:** snapshot byte limit is still checked after subprocess completion, not enforced during streaming.
- **P2-02:** signed manifest expiry, invalidation generation, and verification-policy fields are not fully enforced by qualification.
- **D01:** MySQL Shell fallback is incomplete.
- **D02:** full crash reconciliation is incomplete.
- **D03:** operational custody, SID configuration, and escrow are pending.
- **D04:** positive operational purge execution remains unverified.
- **D05:** consolidated independent T02D review remains pending.

P2-01 and P2-02 block future operational qualification enablement. None is represented as resolved. `OperationalPurgeDisabled` is unchanged.

## Source inventory and restrictions

Implementation is contained in `vault/keys.py`, `vault/models.py`, migration 0007, `vault/services.py`, `vault/rotation.py`, configuration, and `vault/tests/test_key_rotation.py`. No operational key rotation, retirement, backup/recovery, or purge was executed. Publication is authorized by IC-023-T02C-2-GIT-01; deployment, key activation, operational actions, and PR merge remain prohibited. Merge requires separate explicit Product Owner authorization.

## FIX-01 targeted review remediation

IC-023-T02C-2-FIX-01 addresses the three P2 findings reported against PR #34 head `343e8d9e20e5faabe610b39d16540f4bcd907bcd`:

- **ROT-P2-01:** preparation previously created an unscoped journal, so pending rotations were invisible to owner conflict and retirement queries. KEK batches are now owner-bounded; preparation locks the global guard and owner, revalidates the immutable candidate digest, persists the owner (and KEK source/target generations) atomically, and rejects overlapping owner work. Ambiguous unfinished legacy KEK/DEK journals fail closed globally.
- **ROT-P2-02:** confirmation expiry was previously compared with time captured before lock acquisition. Execution now obtains fresh trusted server time after the global guard and operation/confirmation/journal locks and uses it for both executor and confirmation expiry. Tests prove that post-wait expiry causes no key or credential mutation.
- **ROT-P2-03:** owner/source/target journal attributes were assigned in memory but omitted from `update_fields`. Completion now persists `owner`, `old_key_version`, and `new_key_version` in the same transaction as cryptographic publication and terminal state. Reloaded KEK and DEK journals contain the verified transformation metadata; rollback leaves no false completion.

Directly affected verification:

- `python manage.py test vault.tests.test_key_rotation.KeyRotationTests --settings=config.settings.test -v 2` — 9 run, 9 passed, 0 skipped.
- `python manage.py test vault.tests.test_key_rotation.NativeMySQLKeyRotationConcurrencyTests --settings=config.settings.local -v 2 --noinput` — 1 run, 1 passed, 0 skipped on disposable `test_my_database`, which Django destroyed afterward.
- No schema change was required. Django system check, migration drift, cached diff, and secret-safety checks are publication gates.

The corrective commit uses message `fix(vault): address IC-023-T02C-2 rotation review findings`; its canonical SHA is the commit containing this section and the updated PR #34 head. Changed source is limited to `vault/rotation.py`, `vault/tests/test_key_rotation.py`, and this document.

Remaining T02D items are unchanged: L01 interrupted-operation reconciliation, L02 unverified native interleavings, L03 operational custody/ACL/SID/activation/escrow, P2-01 snapshot streaming-size enforcement, P2-02 signed-manifest validity enforcement, and D01–D05. Operational rotation/retirement remains prohibited, operational destructive purge remains under mandatory HOLD, and PR #34 merge remains prohibited without separate Product Owner authorization.
