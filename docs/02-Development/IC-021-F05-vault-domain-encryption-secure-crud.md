# IC-021 — Vault domain, encryption, and secure CRUD

**Status:** IMPLEMENTED ON DRAFT BRANCH — SOL G2 PENDING

**Authorized baseline:** `2c8910e3907d847d4634d225ee44dcf624d1e744`

**Branch:** `feature/ic-021-vault-domain-encryption-crud`

**Authority:** Product Owner authorization for IC-021 only

**Contract:** [F-05 consolidated G1 proposal](../features/F-05-consolidated-g1-proposal.md)

## Checkpoint and source decisions

This is the single primary TTDM C4 checkpoint record. IC-021 implements the ratified F05-D01–D05, D07, D10–D14 foundations without changing those decisions. F05-D06/D08 production grants and reauthentication remain IC-022; F05-D09/D15 UI behavior, full rotation, purge, and recovery remain IC-023. IC-024 remains deferred. No merge or later-task authorization is implied.

## Implemented boundary

- `VaultRecord` stores UUID identity, server-owned protected ownership, four controlled credential types, metadata, active/deleted lifecycle, optimistic revision, explicit schema/envelope/key versions, and AES-GCM nonce/ciphertext/tag columns.
- `VaultOwnerKey` stores only versioned per-owner DEKs wrapped by an external KEK. The KEK is loaded from exactly one of an injected `VAULT_KEK_BASE64` process secret or `VAULT_KEK_FILE`; it is never stored in MySQL or Git.
- AES-256-GCM uses fresh 96-bit nonces, 128-bit tags, and canonical AAD binding owner, record UUID, credential type, and schema. Key wrapping binds owner and key version.
- Internal services implement create, partial update, reveal, reversible delete, restore, metadata list/detail, a 1,000-record active-plus-deleted cap, and global user-before-record/key locking. Critical state and audit writes share one transaction.
- Reveal returns a `DeferredReveal` that rejects plaintext access until the transaction commit callback runs. Audit or commit failure therefore cannot release plaintext.
- Metadata GET routes are authenticated and owner-scoped. Sensitive production POST/PATCH/DELETE/reveal/restore routes are explicitly disabled with a safe `503`; Internal sensitive-service behavior is exercised through explicit test-only mocking of the authorization boundary. No production-importable test authorization issuer is provided.
- Vault audits contain controlled action, actor snapshot, opaque record UUID, target type, outcome, and timestamp only—never secrets, labels, usernames, request bodies, envelopes, keys, or exception text.

The Django API and vault code share one operating-system process identity. Python module boundaries reduce accidental access but are not OS isolation; host/process controls and careful dependency review remain required.

## Migration and recovery contract

Forward migrations add `vault_vaultrecord`, `vault_vaultownerkey`, their checks/indexes, and controlled vault audit vocabulary. No accepted historical migration is edited. Owner deletion is protected. There is no implicit tombstone purge or audit deletion.

Database and KEK backups must be coordinated. Restoring only one side may make records permanently unreadable. IC-021 preserves key/envelope versions but does not add rotation, retirement, backup-manifest, or recovery commands. Old key material must not be retired until the separately authorized F05-D12 historical-backup verification contract is implemented. No administrative or password-derived recovery bypass exists.

## Acceptance traceability

| Criterion | IC-021 evidence/status |
| --- | --- |
| AC-01 | Forward models/migrations, constraints/indexes, drift and apply tests; native MySQL apply/test evidence. Rollback verification is recorded below. |
| AC-02 | Four type contracts, field/byte/control validation, bounded metadata serialization, owner quantity cap tests. |
| AC-03 | AEAD round-trip, nonce uniqueness, bit mutation, tag/nonce mutation, AAD owner/record/type substitution, invalid version tests. |
| AC-04 | External KEK loader, wrapped DEKs only, strict format/length and wrong/missing-key failure; recovery operations deferred. |
| AC-05 | Active-owner and owner-scoped queries; anonymous, cross-owner, admin/staff/superuser, missing/deleted behavior; sensitive routes CSRF protected and disabled. Full IT-role matrix remains a G2 verification item. |
| AC-06 | CRUD/lifecycle/revision services, audit rollback, and post-commit plaintext barrier tests. Production grant integration is deferred to IC-022. |
| AC-07 | Native MySQL independent-connection concurrent update test gives one commit and one conflict. Reveal/delete, restore/purge, rotation, and rewrap integrated races depend on IC-022/IC-023 operations and remain deferred. |
| AC-08 | Metadata/audit/error assertions and repository scan; browser payload inventory awaits IC-023 UI. |

## Validation checkpoint

Environment: Windows, Python 3.13, Django 5.2.8, cryptography 46.0.3, mysqlclient 2.2.7, native MySQL service on `127.0.0.1:3306`. Private environment values were loaded without printing them.

Executed evidence at this checkpoint:

- `python manage.py test vault --settings=config.settings.test -v 1` — PASS, 25 tests with one native-only test explicitly skipped, SQLite support run.
- `python manage.py test vault --settings=config.settings.local -v 1` — PASS, 25 tests, native MySQL; includes separate-connection concurrent updates and native envelope-length checks.
- `python manage.py check --database default` with local settings — PASS.
- Disposable SQLite `migrate` all → `migrate vault zero` → `migrate vault` — PASS; forward apply, rollback, and reapply succeeded.
- `python manage.py makemigrations --check --dry-run --settings=config.settings.test` — PASS, no drift.
- `python manage.py test accounts session_auth security_audit vault --settings=config.settings.test -v 1` — PASS, 132 tests with 19 pre-existing environment/engine skips.
- `npm run validate` — PASS, structure and `.env.example` scan.

The final PR head and SOL exact-head status will be appended after the implementation commit. Tests unavailable because later operations do not yet exist are reported as deferred, never as passing.


## SOL G2 remediation checkpoint — 2026-11-14

**PR:** #28
**Original reviewed head:** `f3789ebb48f22e31f464495299803b9d5cb43efe`
**Original SOL G2 verdict:** CHANGES REQUIRED.

### Remediation status

- G2-R01 HIGH: Production-deny-by-default authorization; test-only mocking.
- G2-R02 HIGH: DeferredReveal plaintext creation only after transaction commit.
- G2-R03 MEDIUM: Generic unavailable handling for malformed UUIDs.
- G2-R04 MEDIUM: Strict HTTPS-origin canonicalization.
- G2-R05 MEDIUM: Native MySQL concurrency verification at the exact 1,000-record cap.
- G2-R06 MEDIUM: Living documentation and acceptance evidence update in progress.

### Latest verification

- SQLite vault suite: 39 tests; 36 passed; 3 skipped.
- Native MySQL vault suite: 39 tests; 39 passed.
- Native MySQL concurrency suite: 3 tests passed.
- Migration drift: No changes detected.
- Git whitespace check: No whitespace errors; LF-to-CRLF warnings only.

### Remaining limitations

- Denial-audit autocommit warnings were observed in test transactions.
- Complete IT-role authorization coverage remains subject to G2 review.
- IC-022 grant integration and IC-023 UI/rotation/recovery remain deferred.
- Independent SOL G2 exact-head review is required.

No commit, push, merge, or subsequent task authorization is implied.

## Outstanding dependencies

- IC-022: password reauthentication, MySQL throttling, exact-session single-use grants, production sensitive-route enablement, and integrated grant-consumption races.
- IC-023: UI reveal/clipboard behavior, full rotation/rewrap, explicit purge, coordinated backup/recovery and historical-key retirement operations.
- Audit retention has no approved duration; any dependent purge remains blocked.
