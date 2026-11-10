# F-05 G1 — Consolidated Requirements and Security Architecture Contract

**Status:** **PRODUCT OWNER RATIFIED — F-05 G1 COMPLETE**

**Feature:** F-05 — Personal Credential Vault

**Task range:** IC-021–IC-023

**Deferred dependency:** IC-024 — permanent account deletion and cleanup

**Discovery authority:** Product Owner-authorized G1 discovery only

**Executor / reviewer:** Codex / SOL

**Verified baseline:** `origin/main` at `d3ced0921601cef762f9ec5cdf6d98755fe4c5c6` on 2026-11-10

**Exact SOL-reviewed PR head:** `4b9276691f8b8135534d87ed2905f0456f81d351`

**SOL G1 review:** PASS on 2026-11-10

**Product Owner ratification:** 2026-11-10; consolidated contract and F05-D01–D15 accepted

**Implementation gate:** IC-021, IC-022, and IC-023 require separate explicit implementation authorization

The Product Owner explicitly accepted SOL's PASS recommendation at exact reviewed head `4b9276691f8b8135534d87ed2905f0456f81d351` and ratified this consolidated F-05 contract together with F05-D01–D15. Requirements expressed as **must** are therefore the G1 requirements baseline. Ratification does not authorize implementation, migrations, dependencies, implementation branches, PR merge, deployment, provider activation, or IC-024. IC-021–IC-023 remain blocked pending separate explicit implementation authorization and their later TTDM gates.

## 1. Authority and source inventory

### 1.1 Authority hierarchy

1. Product Owner decisions and merged closeout evidence are authoritative.
2. Ratified task/feature specifications remain authoritative within their scope.
3. Historical proposals remain evidence of their then-current gate; later accepted records supersede their status, not their history.
4. The recommendations recorded at the SOL-reviewed head became approved F-05 decisions only through the Product Owner's 2026-11-10 ratification. Their discovery origin and approved disposition remain traceable in Section 4.

### 1.2 Inspected baseline

| Source | Status and relevance |
| --- | --- |
| `docs/process/TTDM-WA-001.md` | Approved governance: G1 is a Product Owner requirements gate; SOL reviews G2; task and feature merges require their own gates. Maps IC-021–IC-023 to F-05 and defers IC-024. |
| `docs/features/README.md` and `docs/tasks/README.md` | Registry/index. No IC-021–IC-024 task records exist at the verified baseline. |
| `docs/product/mvp-requirements.md` | Approved technology direction: Next.js/TypeScript, Django/DRF, MySQL; secure credential handling is planned but not specified. |
| F-01 records; IC-003–IC-005 records; `session_auth` | Accepted email identity, server-side database sessions, CSRF on unsafe requests, exact-origin credentialed browser access, structured errors, session rotation/logout, active-account checks, and the Next.js authenticated shell. |
| F-02 records; IC-006–IC-008 and F02-SEC-001 records; `accounts` and `security_audit` | Merged invitation/lifecycle/audit controls: App Admin separation, immediate deactivation denial, all-session revocation, fresh login after reactivation, controlled immutable audit vocabulary, and atomic critical audits. IC-024 remains deferred. |
| F-03 consolidated contract, implementation/acceptance/IC-030 records | Accepted patterns for UUID/private objects, owner-scoped query/service authorization, generic unavailable responses, native-MySQL locking, optimistic revisions, critical-audit rollback, private/no-store responses, compensation, reconciliation, and coordinated database/artifact backup. |
| F-04 consolidated contract and PR #26 closure record | Accepted owner-private conversations, request-time reauthorization, provider-disabled/private-transfer gates, and isolation from private storage. No Copilot-to-vault access exists. |
| `docs/architecture/overview.md`, `docs/architecture/data-model.md`, audit model/service | Current Django/DRF/MySQL boundaries and secret-free, allowlisted audit schema. No F-05 model, API, key service, or encryption dependency exists. |

Before this ratification, no repository record existed for IC-021, IC-022, IC-023, or IC-024 beyond planning references and the explicit IC-024 deferral. The inherited IC-003 policy invariant remains authoritative: an active authenticated owner may access their own vault; App Admin, framework flags, and IT roles grant no cross-owner vault access. The additional requirements below are now the ratified F-05 G1 baseline, not implementation authorization.

## 2. Existing approved requirements

The following are inherited and were not reopened by F-05 ratification:

- Vault data is owner-private. No App Admin, `IT_DOC_ADMIN`, `IT_EDITOR`, `IT_MEMBER`, staff, or superuser flag grants another user's access.
- Unknown, anonymous, inactive, deactivated, and cross-owner subjects are denied by default. Authorization must be enforced server-side on every request; browser state is not authority.
- Browser mutations use the accepted session and CSRF contracts. Unsafe requests without a valid session/CSRF token fail using the established structured error envelope.
- Deactivation removes all database sessions, subsequent protected requests are denied, and reactivation requires a fresh login. Already-running requests cannot be recalled, so sensitive operations must revalidate inside their transaction.
- Critical state changes and their required audit events succeed atomically or fail closed. Denied-attempt audit is bounded best effort and cannot weaken denial.
- Audit rows contain controlled identifiers and outcomes, never passwords, tokens, cookies, session identifiers, request bodies, document content, or vault values. There is no approved automatic audit-retention deletion.
- Provider activation and private-data transfer remain disabled. F-04 must not read vault tables, encryption keys, decrypted values, or vault APIs.
- IC-024 is not authorized. A deletion-review record is not permission to delete an account or vault.

## 3. Ratified F-05 product requirements

### 3.1 Product boundary and record types

F-05 is an owner-private personal vault for credentials needed by that owner. It is not an enterprise password manager, shared-secret store, provider credential broker, document attachment store, browser extension, autofill system, or administrator recovery console.

Ratified record types and fields:

| Type | Nonsecret fields | Encrypted fields |
| --- | --- | --- |
| `LOGIN` | ID, owner ID, label, service/site label, optional canonical HTTPS origin, revision, timestamps | username/account identifier, password, notes |
| `API_TOKEN` | ID, owner ID, label, service label, revision, timestamps | token, optional token prefix/identifier, notes |
| `SSH_KEY` | ID, owner ID, label, revision, timestamps | private key, optional passphrase, notes |
| `GENERIC_SECRET` | ID, owner ID, label, revision, timestamps | secret value, optional account identifier, notes |

The server must not derive or persist a public fingerprint from a secret unless a later approved use case requires it. Public key material for `SSH_KEY` is excluded from the initial record unless the PO explicitly approves storage and derivation behavior.

Ratified limits: label 120 characters; service label 120; origin 2,048; account identifier 320; primary secret 32 KiB UTF-8; notes 8 KiB; private key 64 KiB; list default 25 and maximum 100; at most 1,000 active/deleted records per owner. Values are text in V1; binary secrets and attachments are excluded.

### 3.2 Encryption envelope

- Every secret-bearing record must use authenticated encryption. Encryption must provide confidentiality and integrity; decryption must authenticate before returning plaintext.
- Ratified algorithm: AES-256-GCM with a fresh cryptographically random 96-bit nonce for every encryption and a 128-bit tag. Algorithm/version, key version, nonce, ciphertext, and tag are stored separately. Nonce reuse under the same key is forbidden and tested.
- Associated authenticated data (AAD) must bind a versioned context plus immutable record ID, owner ID, record type, and schema version. Moving ciphertext between records, owners, or types must fail authentication.
- No plaintext credential value may be stored in MySQL, audit, logs, exceptions, caches, analytics, fixtures, snapshots, URLs, or browser persistence.
- Encryption/decryption exists behind one narrow service. Models, serializers, views, Copilot, document services, templates, and generic debugging tools must not call cryptography primitives or key storage directly.
- Decryption or key-version failure is a generic unavailable failure; the server must not return partial plaintext or distinguish tamper, missing key, malformed envelope, or wrong owner to the caller.

### 3.3 Key hierarchy, separation, rotation, and recovery

Ratified local-MVP hierarchy:

1. A 256-bit root key-encryption key (KEK) is generated outside MySQL with an OS cryptographic RNG.
2. A random per-owner data-encryption key (DEK) encrypts credential records. The KEK wraps each DEK with authenticated encryption and owner-bound AAD.
3. MySQL stores only wrapped DEKs, key versions, and ciphertext envelopes. The KEK is loaded only by the Django API process from a service-controlled file or injected process secret; it is never committed or stored in MySQL.
4. Only the Django API process hosting the narrow vault service receives the online KEK. The Next.js process/client bundle, document-processing worker, retrieval/index worker, Copilot/provider adapter, and every unrelated command receive no vault key, key-file path, unwrap interface, or decrypt capability. A dedicated vault rotation/recovery command may receive key access only for a separately approved operation and must not share that access with general workers.

Rotation has two layers: KEK rotation rewraps DEKs without decrypting every credential; DEK rotation decrypts and re-encrypts an owner's records under a new DEK. Rotation must be resumable, versioned, locked per owner, and leave either the old valid envelope or the new valid envelope—never an unmarked mixture. A durable rotation journal records rotation ID, old/new key versions, bounded batch cursor, state, and last committed checkpoint. Each envelope identifies its key version, so restart revalidates the journal and resumes idempotently from committed state while both keys remain available.

Key retirement has two distinct stages. **Online retirement** stops new writes with a key and may remove it from the live API key set only after the current database, restorable tombstones, incomplete rotation journals, and every retained backup manifest have been inventoried. **Cryptographic destruction** is later and is prohibited while any retained historical backup set references the key. The nonsecret backup-manifest inventory must record backup-set ID, database snapshot ID, key-bundle ID, included key versions, creation/retention state, application/schema version, verification status/time, and destruction disposition. Before online retirement, rotation must be complete and restart-tested, a matched post-rotation checkpoint must pass an isolated restore plus no-plaintext authentication scan, and each retained historical backup must either retain its referenced old key in its protected bundle or be expired and destroyed under a separately approved retention policy. Before cryptographic destruction, no live/restorable row, journal, retained manifest, legal/operational hold, or recoverable backup may reference the key; an independently checked inventory and critical audit are required. A key is never destroyed merely because the current database no longer references it.

Key loss is intentionally not bypassable: without an applicable KEK/DEK, credential values are unrecoverable. App Admin cannot reset or escrow an owner password to recover vault content. Recovery restores a mutually consistent database and key backup; it must never substitute a new key and claim old ciphertext is recoverable.

### 3.4 Ownership and secure CRUD

- The server assigns owner from the authenticated actor. Clients cannot supply or change `owner_id`.
- List returns only the caller's nonsecret metadata. It never decrypts values and never returns secret fields, ciphertext, nonce, tag, wrapped keys, key versions, deletion metadata, or cross-owner counts.
- Detail returns only nonsecret metadata. Reveal is the only read contract that returns a credential value.
- Create accepts a sensitive value, validates and encrypts it before persistence, and returns metadata only. It requires a valid sensitive-operation grant.
- Update requires expected revision, a valid grant, row lock, fresh owner/active-state revalidation, a new nonce for every changed encrypted envelope, and atomic audit. Omitted secret fields retain their values; an explicit replacement is distinguishable from omission without echoing the old value.
- Delete is owner-only, grant-protected, and initially a reversible tombstone. Normal queries and reveals exclude tombstones. Restore is grant-protected and permitted during the approved restoration window.
- Duplicate labels and duplicate secret values are allowed; the service performs no cross-owner or global equality test.
- Missing, deleted, cross-owner, malformed, tampered, and unauthorized IDs use a generic unavailable contract so direct-object requests are not an existence oracle.
- Optimistic revision conflicts return a safe `409`; the response contains no current secret or submitted value.

### 3.5 Reauthentication and short-lived grants

Sensitive operations are create, reveal, encrypted-field update, delete, restore, DEK rotation, and any future export. Listing and metadata detail require an active session but no grant.

Ratified flow:

1. `POST /api/v1/vault/reauthenticate` receives the account password over the existing authenticated, CSRF-protected session.
2. The server reloads the active user, verifies the Django password hash, rotates no session, and creates a server-side sensitive-operation grant. Password input is never logged, audited, stored, or returned.
3. A grant is bound to the user ID and the exact current Django session using a one-way digest of the session key plus a server-side grant pepper/context. Raw session keys and raw grant tokens are not stored.
4. The server returns a random opaque bearer proof once. The browser holds it only in component memory and sends it in a dedicated header. It must not enter a URL, cookie, HTML serialization, service worker, local/session storage, IndexedDB, cache, telemetry, or console.
5. The grant expires two minutes after issuance by absolute server time; use does not slide expiry.

Ratified grant semantics are **single-use reservation and consumption**: each grant authorizes at most one committed sensitive operation. “Reservation” means holding the grant row lock inside the transaction; there is no separately committed reserved state. The transaction locks and validates the active user and exact session before the grant, then validates target/business preconditions. Two concurrent requests with the same proof serialize on that row and at most one can commit consumption.

Ratified grant failure and delivery table:

| Outcome | Grant state | Target/audit state | Response and retry contract |
| --- | --- | --- | --- |
| Authentication, CSRF, proof lookup/digest, user/session, expiry, or prior-consumption denial before a valid grant is reserved | Unchanged; no valid grant is identified or reserved | No sensitive target change; bounded secret-free denial audit only | Generic denial. A caller may submit another proof, but this request receives no retry assurance. |
| Valid grant reserved, then payload, revision, target lifecycle, authorization, or other business precondition rejects the operation | Consumed in the same committed transaction | No target mutation; one controlled critical `grant.used` denied/conflict event with no probed cross-owner ID | Safe 400/403/404/409 as applicable. The proof cannot be replayed; the owner must reauthenticate. |
| Crypto, critical-audit, database write, deadlock exhaustion, or commit failure before durable commit | Transaction rolls back; grant remains unused unless its independent absolute expiry passes | Target, consumption, and critical audit all roll back; any plaintext buffer follows the best-effort lifecycle below | Generic `service_unavailable`; the client may retry the same proof while still valid, but success is not promised. Internal deadlock retry is bounded to two complete transaction attempts and revalidates all state. |
| Successful non-reveal mutation | Consumed at the same commit as target mutation and critical audit | One committed mutation/audit outcome under the grant uniqueness and row locks | Respond only after commit. A lost response does not undo the mutation; replay is denied. Client reconciles through metadata/revision rather than assuming failure. |
| Successful reveal | Consumed at the same commit as the critical reveal audit; target remains unchanged | Plaintext may exist only in process memory pending commit and is not handed to response rendering before commit succeeds | After commit, make at most one HTTP response attempt. If transport/serialization fails, the grant remains consumed and delivery is unknown; the client must reauthenticate. |
| Exception after commit, including connection loss while sending a mutation or reveal response | Already consumed | Already committed target/audit state | Never roll back or reuse the grant. No exactly-once delivery is claimed; server-side committed effect/release attempt is at most once, while client receipt is unknowable. |

Serialization plus the grant's single committed transition provides at-most-once committed sensitive use. It does **not** provide exactly-once HTTP delivery, and automatic client replay of a sensitive request is forbidden. Only the bounded server-side transaction retry described above is permitted, and it must occur before any commit or plaintext response handoff.

All outstanding grants are revoked on logout, deactivation, password change, explicit `POST /api/v1/vault/grants/revoke`, and server-detected session invalidation. Because ordinary session expiry/deletion can occur without a grant-row update, every use must independently verify the bound session still exists, is unexpired, decodes safely to the same active user, and remains the request's current session. Malformed or undecodable session state fails closed.

Ratified local-MVP reauthentication throttling uses MySQL—no Redis or in-memory-only authority. After session authentication and CSRF, the service follows the global order by locking the user, exact session, per-user throttle row, and per-session-digest throttle row. Five failed password checks in one fixed 15-minute window blocks reauthentication for both scopes until that window ends; malformed or blank password submissions count after authenticated request validation. A successful password check resets both failure counters. At most three unexpired, unconsumed grants may exist for one session, and at most ten grants may be issued per user in a fixed 15-minute window; issuance counters are updated atomically with grant creation. Concurrent attempts serialize on the user throttle row, so they cannot exceed a limit by racing. Wrong password, inactive state, blocked user/session, and issuance-cap denial return the same fixed `reauthentication_failed` body; throttled cases use `429` with a coarse whole-minute `Retry-After`, while other failures use `403`, without email/account input or account-existence differences. Password hashing work must not be skipped in a way that creates a useful timing oracle. Counters contain only user/session digests, window timestamps, and counts; no password, IP address, email, or proof. This is the ratified F05-D08 default.

### 3.6 Deletion, restoration, and backup consistency

The ratified vault record lifecycle is `ACTIVE → DELETED → PURGED`. Restore is allowed from `DELETED` for 30 days. Purge is an explicit dry-run-first local maintenance operation after the window; it is not IC-024 and never deletes an account. Purge removes the credential ciphertext/envelope and retains only the minimum nonsecret vault tombstone required for reconciliation under the separately controlled retention contract. It does not delete or shorten retention of immutable security-audit events. No numerical audit-retention period is approved; any purge dependent on that undefined policy remains blocked until the policy is explicitly approved, and no audit purge is authorized by F-05 G1.

Database and key material form one recovery set. Before key rotation, bulk reconciliation, or purge, record a checkpoint containing database backup identity, key bundle identity/version inventory, application commit/schema, rotation-journal state, timestamp, retention state, and verification result. Back up keys and database separately with least privilege but bind them by a nonsecret manifest registered in the retained-backup inventory. A restore is acceptable only if every key version referenced by that historical database is present in its matched protected key bundle, its manifest identity/digests verify, incomplete rotations can resume, and every restored wrapped DEK/ciphertext authenticates in a no-plaintext verification pass. Recovery verification decrypts only inside the controlled verifier, authenticates expected context, records counts/safe codes, and discards buffers without emitting values. A newer database with older keys, an older database without its historical keys, or an unregistered/partially destroyed backup fails closed. Successful restore testing is required before a backup set can support a retirement decision.

### 3.7 Audit, browser, clipboard, cache, and error controls

Controlled success/failure/denial vocabulary must cover reauthentication, grant issuance/revocation/use, create, update, reveal, delete, restore, rotation, recovery verification, and purge. Events contain action, actor snapshot, vault-record opaque ID where authorized, outcome, timestamp, and safe correlation only. They contain no label, origin, username, token prefix, ciphertext, key version, secret length, submitted body, exception, session/grant value, or clipboard state. Cross-owner and unavailable denials omit the probed record ID.

Reveal responses must set `Cache-Control: no-store, private`, `Pragma: no-cache`, and `X-Content-Type-Options: nosniff`; no secret is server-rendered. The service may decrypt into a request-local buffer while its transaction is open, but response construction/iteration and socket handoff are barred until grant consumption and the critical reveal audit commit successfully. On rollback the buffer reference is dropped and no plaintext response is created. After commit, failure to serialize or deliver cannot restore the grant and the server cannot know whether the client received bytes. The frontend keeps plaintext only in the smallest component state needed, clears it on timeout, navigation, tab visibility loss, mutation completion, error, logout, and unmount, and must not place it in global stores. Reveal defaults masked and automatically clears after 30 seconds.

Clipboard copy is an explicit user action. The UI warns that the operating-system clipboard is outside application control, uses the Clipboard API only in a secure context, attempts best-effort overwrite after 30 seconds only if the clipboard still contains the copied value, and never claims guaranteed erasure. JavaScript strings, framework/runtime copies, browser history internals, process memory, swap, crash dumps, and the OS clipboard cannot be proven securely erased; clearing references and overwriting are exposure-reduction measures only. Under ratified F05-D15, clipboard copy is not audited; reveal remains audited.

API errors use stable generic codes and no exception text. Encryption, database, key, and audit failures return no submitted or existing plaintext. Error-reporting integrations, request-body logging, DRF browsable forms, Django debug pages, React error payloads, source maps exposed to untrusted clients, and analytics capture must be inspected or disabled at the sensitive boundary.

## 4. Ratified Product Owner decision register

The Product Owner ratified every SOL-recommended default below on 2026-11-10 at reviewed head `4b9276691f8b8135534d87ed2905f0456f81d351`. `RATIFIED` makes each choice part of the F-05 G1 requirements baseline; it does not authorize IC-021–IC-023 implementation or PR merge.

| ID | State | Decision | Approved default and retained trade-off |
| --- | --- | --- | --- |
| F05-D01 | RATIFIED | Credential record types and field/size limits | Section 3.1 types and limits. A smaller type set simplifies validation; SSH keys add parser/format and larger-value risk. |
| F05-D02 | RATIFIED | Encryption primitive/library | AES-256-GCM through a maintained Python cryptography library. GCM is standard and fast but nonce uniqueness is critical; a new dependency requires supply-chain review during separately authorized implementation. |
| F05-D03 | RATIFIED | Key hierarchy | Per-owner DEKs wrapped by an external KEK. Better blast-radius and efficient KEK rotation than one global data key, at added schema/recovery complexity. |
| F05-D04 | RATIFIED | KEK storage | Service-controlled local file or injected process secret for the local MVP. It is simpler than KMS but makes host ACLs, diagnostics, and coordinated backups critical. |
| F05-D05 | RATIFIED | Recovery/escrow posture | No administrative or password-derived recovery bypass; recovery requires coordinated key/database backups. Key loss can be permanent; no escrow is approved. |
| F05-D06 | RATIFIED | Grant behavior | Two-minute absolute TTL, single-use, exact-session-bound, transactionally consumed grants. Repeated sensitive operations require repeated reauthentication. |
| F05-D07 | RATIFIED | Grant consumption and rollback semantics | Follow Section 3.5: consume after authenticated target/business rejection; retain only after complete pre-commit rollback with no state change or plaintext release; no exactly-once HTTP delivery claim. |
| F05-D08 | RATIFIED | Password reauthentication and throttle | Existing account password plus five failures per user/session per fixed 15 minutes, three live grants per session, and ten issuances per user per 15 minutes using MySQL serialization. Password change/reset revokes grants; passwords never derive or recover vault keys. |
| F05-D09 | RATIFIED | Reveal and clipboard timers | Clear reveal state and attempt best-effort clipboard overwrite after 30 seconds. Memory and clipboard erasure cannot be guaranteed. |
| F05-D10 | RATIFIED | Deleted-record window and purge | Thirty-day reversible vault tombstone followed only by explicit dry-run/execute credential purge. This does not authorize audit deletion or IC-024. |
| F05-D11 | RATIFIED | Credential/tombstone and audit retention | Credential/tombstone retention and audit retention require separate controls. **No numerical audit-retention duration is approved. Any purge dependent on an undefined retention policy remains blocked until that policy is explicitly approved; no unapproved audit purge is permitted.** |
| F05-D12 | RATIFIED | Rotation trigger and old-key retirement | Manual approved operator action for V1; no scheduled rotation. Journal completion, current/historical backup-manifest inventory, matched restore/crypto-check, and retention disposition precede retirement or destruction. |
| F05-D13 | RATIFIED | Search/filter | Metadata-only exact type and bounded label/service prefix filtering. Search over encrypted values and leakage-prone deterministic indexes are excluded. |
| F05-D14 | RATIFIED | Per-owner quantity cap | Maximum 1,000 active/deleted vault records per owner, bounding list, rotation, backup-verification, and denial-of-service cost. |
| F05-D15 | RATIFIED | Clipboard-copy audit | Do not audit clipboard copy; credential reveal remains audited. Clipboard success or erasure cannot be reliably attested. |

The approved defaults remain subject to the security invariants and verification gates in this contract. Changing one requires a separately reviewed requirements decision; ratification itself still supplies no implementation authority.

## 5. Threat model and trust boundaries

### 5.1 Protected assets and adversaries

Assets are plaintext credentials, ciphertext integrity, KEK/DEKs, grant proofs, account passwords, ownership metadata, audit integrity, and recoverability. In-scope adversaries include another authenticated user, an App Admin or IT-role user without ownership, a caller replaying object IDs/grants, CSRF/web-origin attackers, browser scripts accidentally persisting values, log/telemetry readers, database-only disclosure/tampering, concurrent requests, stale sessions, and operational restore/key mismatch.

Trusted for the local MVP: the Django API process while handling a vault request, Python/crypto runtime and OS RNG, MySQL for availability/transaction ordering but **not plaintext confidentiality**, the service identity and its protected key-file ACL, and approved backup custodians. The vault module shares the Django API process identity with other Django apps; module/import restrictions are code-level least privilege, not OS/process compromise isolation. Actual process/key-access boundaries must be verified during IC-021 before any stronger isolation claim. OS administrator/SYSTEM, arbitrary code execution as the service identity, malicious browser extensions, an already-compromised owner endpoint, memory scraping of the API process, and physical host compromise are outside what application encryption alone can defeat and must be recorded as residual risk.

### 5.2 Boundary and failure-closed matrix

| Boundary | Required control | Failure-closed behavior |
| --- | --- | --- |
| Authentication/authorization | Current session, active owner reload, CSRF, owner-scoped queryset/service, in-transaction revalidation | Generic 401/403/404; no record existence or metadata; no grant use or audit secret |
| Encryption/decryption | Versioned envelope, fresh nonce, owner/record/type AAD, centralized service | No plaintext/partial result; generic unavailable; controlled failure audit without envelope details |
| Key availability/loss | External KEK, wrapped per-owner DEK, key-version inventory | Writes/reveals stop; listing metadata may remain available only if it cannot misstate recoverability; no fallback key or auto-regeneration |
| Sensitive grant | Password verification, random proof, hashed storage, exact session binding, two-minute absolute expiry, single-use row lock | Invalid/expired/revoked/replayed/concurrent proof denied identically; no operation proceeds |
| Reveal/mutation | Global lock order, revision, active owner and grant recheck, commit barrier, no-store response | Audit or DB failure prevents commit/release; plaintext is not handed to the response before commit and is never included in error |
| Audit/transaction | Critical event inside same atomic mutation; bounded denial audit | Critical audit failure rolls back. Denial audit failure never grants access and emits only a fixed secret-free warning |
| Backup/restore | Bound DB/key manifest, all-key inventory, authentication verification | Mismatch blocks service/recovery declaration; no partial restore, key retirement, or purge |
| Copilot/documents | No imports/routes/service credentials; separate app boundary and process key distribution | Vault access absent even when provider is later enabled; private transfer gate cannot authorize vault data |

## 6. Ratified Django/DRF and MySQL architecture

### 6.1 Components

- New `vault` Django app owns models, migrations, policies, serializers, services, API views, reconciliation/rotation commands, and tests.
- `VaultRecord` stores UUID, owner FK with protected deletion, type, nonsecret metadata, lifecycle, revision, timestamps, and the versioned ciphertext envelope. Database checks constrain type/lifecycle/version and ensure envelope columns are all present or all absent only where the approved lifecycle permits.
- `VaultOwnerKey` stores one active and bounded historical wrapped DEK per owner with key version and lifecycle. A native MySQL uniqueness constraint enforces one active owner-key version.
- `SensitiveOperationGrant` stores a random UUID identity, user FK, session-binding digest, proof digest, issued/expiry/consumed/revoked timestamps, and reason. It never stores a raw proof or session key. Native checks constrain timestamp combinations; service transactions enforce semantics that cannot be expressed as checks.
- `vault.crypto` exposes `encrypt`, `decrypt`, `wrap`, `unwrap`, and envelope validation through typed versioned contracts. It obtains the KEK from a dedicated settings/provider boundary that validates exact length/format and never prints it.
- `vault.services` is the only business entry point. Views do not access models or crypto directly for sensitive operations.
- Existing `security_audit` is extended only by a forward migration with controlled vault actions/target type. Existing migrations are never edited.
- The Next.js vault page consumes versioned APIs through the shared credentialed/CSRF client. Plaintext state is local and ephemeral.

### 6.2 Ratified API contract

All responses use `{"error":{"code":"...","message":"..."}}` on error. Mutations require CSRF. IDs are UUIDs. Metadata serializers never include an encrypted value or envelope field.

| Method and route | Grant | Success contract |
| --- | --- | --- |
| `GET /api/v1/vault/credentials?cursor=&type=` | No | `200 {"credentials":[metadata...],"nextCursor":...}`; owner-only bounded keyset page |
| `GET /api/v1/vault/credentials/{id}` | No | `200 {"credential":metadata}` |
| `POST /api/v1/vault/reauthenticate` | Password creates grant | `201 {"grant":"<one-time-proof>","expiresAt":"..."}`; `Cache-Control: no-store` |
| `POST /api/v1/vault/grants/revoke` | Current session | `204`; revokes all current-session vault grants by default |
| `POST /api/v1/vault/credentials` | Yes | `201 {"credential":metadata}` |
| `PATCH /api/v1/vault/credentials/{id}` | Yes | `200 {"credential":metadata}`; requires `expectedRevision` |
| `POST /api/v1/vault/credentials/{id}/reveal` | Yes | `200 {"credential":{"id":"...","revealed":{...}}}`; no-store; only fields appropriate to type |
| `DELETE /api/v1/vault/credentials/{id}` | Yes | `204`; reversible tombstone, not physical purge |
| `POST /api/v1/vault/credentials/{id}/restore` | Yes | `200 {"credential":metadata}` |

Grant proof is sent as `X-Vault-Grant`; the response field name and header contract are part of the ratified G1 baseline. The header must be redacted by every server/proxy logger and must not be allowed cross-origin beyond the existing exact frontend origin. `invalid_grant`, `credential_unavailable`, `conflict`, `invalid_request`, `key_unavailable`, and `service_unavailable` are the ratified safe-code set; messages remain fixed and non-diagnostic.

### 6.3 Global transaction and lock order

F-05 must extend, not invert, the accepted F-02 ordering. The global order for rows that an operation actually needs is:

1. `AdminLifecycleGuard` singleton, **only** for existing F-02 operations whose last-active-admin invariant requires it.
2. `accounts.User`, ordered by numeric ID if more than one.
3. `django_session`, ordered by session key; ordinary vault use locks only the exact current session, while lifecycle/password operations lock affected sessions deterministically.
4. `SensitiveOperationGrant` or throttle rows, ordered by stable primary key; throttle order is per-user then per-session.
5. `VaultOwnerKey`, ordered by owner/key version.
6. `VaultRecord`, ordered by UUID.
7. Critical `SecurityAuditEvent` insert after all required validation/mutation, immediately before commit.

No path may acquire an earlier class after a later class. In particular, **no vault path locks a grant and then a user**. Ordinary grant use locks `User → exact Session → Grant → OwnerKey → VaultRecord`. Explicit grant revocation and logout integration lock `User → exact Session → affected Grants`. Password change locks `User → affected Sessions → affected Grants`; password persistence, session/grant revocation, and critical audit commit atomically under its future approved contract. F-02 deactivation retains `AdminLifecycleGuard → User → affected Sessions` and F-05 extends it with affected grants after sessions. Role-only changes need not touch grants because roles do not grant vault access, but still follow the prefix order.

This ordering gives a deterministic winner. A vault operation that locks the user first may commit before a later deactivation begins; an operation that begins after deactivation commits, or waits behind its user lock, reloads the inactive user and fails. Logout, revoke, and password change similarly serialize through the user/session prefix. Requests already executing before those revocations cannot be recalled, matching the inherited F-02 boundary, but none may commit after a winning revocation transaction whose locks they waited behind.

Crypto should occur outside the transaction only when its inputs are immutable and the final transaction revalidates user, session, grant, key version, record revision, owner, and lifecycle. Otherwise it occurs under the shortest safe locked transaction. The ratified create flow generates an ID/envelope before the final transaction, then revalidates key version and grant under the global order; a key-version change discards the envelope and uses the bounded pre-commit retry. Deadlock retry is at most two complete server-side attempts, never crosses a commit or response handoff, and reruns every authorization/precondition check. Tests must force both winner orders for deactivation, logout, password change, explicit revoke, and grant use using independent MySQL connections and barriers.

### 6.4 Plaintext release commit barrier

Reveal may authenticate/decrypt into request-local process memory before commit, but the plaintext must not be placed in a DRF `Response`, renderer, iterator, template, socket buffer, cache, or callback until the database transaction has durably committed both grant consumption and its critical reveal audit. A transaction commit hook may only mark the request eligible to construct the response; it must not capture plaintext in a long-lived closure. Commit failure returns a generic error and drops the buffer reference. After commit, the service makes one response attempt. A serialization/connection failure leaves the grant consumed and audit committed, and the server cannot distinguish zero, partial, or complete client receipt. Therefore F-05 guarantees at-most-one committed reveal/release attempt, not exactly-once delivery. The browser must reauthenticate rather than automatically replay.

## 7. Functional and nonfunctional requirements

1. Confidentiality: database-only access reveals no plaintext credential or usable DEK/KEK.
2. Integrity: envelope or AAD tampering is detected before plaintext release.
3. Least privilege: only the active owner and vault process with key access can reveal/mutate.
4. Availability: missing keys, crypto failures, database failures, and audit failures fail closed and surface safe actionable status without data exposure.
5. Atomicity: record state, grant consumption, and critical audit follow the ratified failure table; success is never reported for a rolled-back mutation.
6. Concurrency: native MySQL locking/constraints prevent lost updates, duplicate active keys, double grant use, resurrection, and rotation/mutation races.
7. Performance: metadata list/detail do not decrypt. Sensitive operation target is p95 below two seconds for local MVP excluding password-hash cost; no relaxation of password hashing or crypto validation is permitted to meet it.
8. Accessibility: reveal/copy/delete controls are keyboard operable, labelled, focus-safe, and announced without placing plaintext in accessible status/history longer than displayed.
9. Observability: metrics use counts/durations/safe codes only. No high-cardinality record labels, owner email, secret length, envelope, key version, or exception text.
10. Compatibility: F-01–F-04 behavior and migrations remain intact; no AWS, Redis, Celery, external vault/KMS, provider, or deployment change.

## 8. IC-021 — Vault domain, encryption, and secure CRUD

**Objective:** Establish the owner-private vault aggregate, versioned authenticated-encryption boundary, key wrapping, metadata-only listing/detail, and secure create/update/reveal/delete/restore services and APIs.

**Dependencies:** Accepted F-01 authentication/CSRF; IC-003 vault policy; F-02 active-state/audit controls; native MySQL foundation. IC-022 grants may be represented by a test seam until integrated, but production-sensitive routes must remain disabled until IC-022 is accepted.

**Functional requirements:** Sections 3.1–3.4, 3.6–3.7 and 6; forward migrations; explicit envelope/key versions; protected ownership; metadata serializers; revision control; tombstone lifecycle; controlled audit vocabulary.

**Security invariants:** no plaintext persistence; authenticated decryption before release; fresh nonce; owner/record/type AAD; external KEK; no cross-owner/admin/role access; generic unavailable behavior; no sensitive response from a failed transaction; no ciphertext/envelope exposure through APIs.

**Acceptance criteria:**

| ID | Criterion |
| --- | --- |
| IC-021-AC-01 | Native MySQL migrations create constrained/indexed record and owner-key models; apply/check/rollback/drift evidence passes without editing prior migrations. |
| IC-021-AC-02 | Approved record types/limits validate; metadata list/detail never decrypt or expose encrypted fields and are bounded/deterministic. |
| IC-021-AC-03 | Every create/update uses a fresh nonce and approved AEAD; correct context round-trips, while bit flips and record/owner/type envelope swaps fail without plaintext. |
| IC-021-AC-04 | KEK remains outside DB/repository; DB dump contains only wrapped DEKs/ciphertext; missing, malformed, or wrong-version key material prevents sensitive startup/operation safely. |
| IC-021-AC-05 | Owner-only service/query/API enforcement denies anonymous, inactive, all cross-owner, App Admin-only, every IT role, staff, and superuser combinations without existence leakage. |
| IC-021-AC-06 | Create/update/reveal/delete/restore follow metadata/no-store/error/audit contracts and optimistic revisions; audit failure rolls back critical state/release. |
| IC-021-AC-07 | Concurrent update/delete/restore/rotation boundaries preserve one valid revision/lifecycle/key envelope; losing operations return safe conflicts and never overwrite or resurrect. |
| IC-021-AC-08 | Logs, audits, errors, test reports, fixtures, browser payload inventories, and repository scans contain no sentinel credentials, raw keys, grant/session values, or request bodies. |

**Required negative tests:** direct UUID cross-owner access; App Admin/IT-role combinations; inactive owner; missing/invalid CSRF; unsupported type/oversize/control characters; ciphertext/tag/nonce/AAD/key-version tamper; wrong key; deleted/expired restore; stale revision; envelope-column direct corruption; serializer/debug/error leakage.

**Concurrency and rollback tests:** two updates at one revision; reveal versus delete; restore versus purge eligibility; update versus DEK rotation; KEK rewrap interruption; database failure after encryption; audit failure; commit failure; nonce-provider failure. Final state, audit cardinality, revision, envelope authentication, and absence of plaintext must be asserted.

**Living documentation:** following ratified TTDM clarification C4, one primary Markdown task record for each meaningful IC-021 checkpoint by default, plus feature-level, API, data-model, architecture, and key/envelope/rotation runbook updates where necessary. Additional records are optional when they materially improve traceability, not a mandatory four-file pattern. Record source/decision traceability, exact commands/counts/environment, limitations, and exact PR head.

**SOL G2 boundary:** crypto design/dependency review; key separation; migration and native constraints; owner matrix; tamper/rollback/concurrency evidence; secret scans; no production route enabled without IC-022; no IC-024/provider/infrastructure expansion.

## 9. IC-022 — Reauthentication and short-lived grants

**Objective:** Add password reauthentication and server-side, exact-session-bound, two-minute sensitive-operation grants with deterministic expiry, consumption, revocation, and concurrency semantics.

**Dependencies:** F-01 sessions/CSRF; F-02 lifecycle/session revocation; IC-021 service seam and audit vocabulary. No new authentication factor or password-reset flow.

**Functional requirements:** Section 3.5; reauthentication/revocation endpoints; proof hashing; session binding; single-use state machine; absolute server time; password-change/logout/deactivation hooks or request-time invalidation; frontend in-memory handling.

**Security invariants:** password and raw proof are never persisted/logged; a grant is usable only by the issuing active user and exact live session; expiry never slides; at most one concurrent use succeeds; revocation and deactivation win for requests starting after commit; invalid proof/record combinations disclose nothing.

**Acceptance criteria:**

| ID | Criterion |
| --- | --- |
| IC-022-AC-01 | Correct current password on an authenticated CSRF-protected request issues one two-minute no-store proof; wrong/blank/inactive cases share a safe denial and create no usable grant. |
| IC-022-AC-02 | DB stores only proof/session digests and constrained lifecycle timestamps; raw password, proof, and session ID are absent from DB, audit, logs, errors, and browser persistence. |
| IC-022-AC-03 | Exact-session/user binding, absolute expiry boundary, single use, explicit revocation, logout, deactivation, password change, malformed session, and deleted/expired session all fail closed. |
| IC-022-AC-04 | Two native-MySQL requests using one grant produce at most one committed sensitive outcome according to the PO-ratified failure table; no double reveal/mutation/audit occurs and no exactly-once HTTP delivery is claimed. |
| IC-022-AC-05 | Grant consumption and sensitive mutation/audit are transactionally consistent; injected DB/audit/crypto failures match the PO-ratified retain-or-consume rule and never release plaintext. |
| IC-022-AC-06 | The ratified MySQL-backed five-failures-per-user/session per fixed 15-minute throttle, three-live-grant session cap, and ten-issuances-per-user per 15-minute cap serialize under concurrency and use enumeration-safe responses. |
| IC-022-AC-07 | Frontend retains proof/plaintext only in component memory, clears on every specified event, sends the dedicated redacted header, and survives stale/out-of-order responses without restoring cleared data. |

**Required negative tests:** proof replay; proof from another session/user; expired at exact boundary; revoked proof; logout/deactivation/password-change races; missing/invalid CSRF; copied header in URL/body; raw proof in error/console/storage; session decode error; clock control; password oracle and brute-force boundary.

**Concurrency and rollback tests:** concurrent grant use; use versus revoke; use versus deactivation/session deletion; issue versus logout; reservation followed by validation, audit, DB, or crypto failure; deadlock retry. Use independent MySQL connections and event/barrier-controlled ordering, not sleep-based claims.

**Living documentation:** one primary Markdown record per meaningful IC-022 checkpoint by default under C4, with feature-level updates plus the grant state/failure table, endpoint/header contract, lock-order/session invalidation integration, throttle decision, browser-memory evidence, exact G2 head, and residual timing limitations. Extra records are optional, not mandatory.

**SOL G2 boundary:** password-verification safety; proof entropy/hash/session binding; exact expiry and single-use semantics; native races; lifecycle integration; frontend storage/log scans; no MFA/reset/IC-024 or multi-use grant silently added.

## 10. IC-023 — Vault lifecycle, recovery, and integrated acceptance

**Objective:** Complete deletion/restoration/purge, key rotation and coordinated recovery controls, integrate the UI, and prove F-05 end to end while leaving IC-024 deferred.

**Dependencies:** SOL-accepted IC-021 and IC-022; accepted F-01–F-04 baseline. IC-024 depends on IC-023, not the reverse.

**Functional requirements:** owner UI; Section 3.6 backup/restore; dry-run-first bounded reconciliation/rotation/purge commands; key inventory; restore verification; accessible reveal/copy flows; integrated regression and recovery evidence.

**Security invariants:** operator/App Admin authority never grants plaintext; commands identify an approved actor but do not reveal values; purge/rotation/recovery are bounded, resumable, idempotent, locked, and critically audited; database and key backups are accepted only as a matched set; Copilot/documents remain unable to access vault data.

**Acceptance criteria:**

| ID | Criterion |
| --- | --- |
| IC-023-AC-01 | Owner UI completes metadata list/create/update/reveal/delete/restore with grant prompts, safe stale-response handling, no-store behavior, accessibility, and explicit clipboard limitations. |
| IC-023-AC-02 | Deleted records are unavailable normally, restorable only inside the approved window, and purgeable only by explicit bounded dry-run/execute control; no account deletion occurs. |
| IC-023-AC-03 | KEK rewrap and DEK rotation are journaled, versioned, restart-tested, idempotent, race-safe, and recoverable; online retirement and destruction are separately blocked by live/restorable rows, incomplete journals, retained historical-backup manifests, holds, and unresolved verification. |
| IC-023-AC-04 | Matched current and historical DB/key backup restores verify manifest identity/digests and authenticate every envelope without emitting plaintext; mismatched, missing, corrupt, older-key-without-bundle, unregistered, and partial backups fail closed and cannot be declared recovered. |
| IC-023-AC-05 | Deactivation, logout, role/admin changes, session invalidation, and reactivation preserve owner-only behavior and grant revocation; IC-024 remains absent. |
| IC-023-AC-06 | Full backend native-MySQL, frontend unit, typecheck, lint, production build, and real-browser workflows pass with exact commands/counts and honest limitations. |
| IC-023-AC-07 | Synthetic sentinel scanning proves secrets absent from logs, audit, errors, SSR/build output, URLs, browser storage/cache, console, analytics, and unrelated F-03/F-04 responses. |
| IC-023-AC-08 | Repository dependency/import/route tests prove Copilot, provider adapter, document services/workers, and non-vault commands have no vault decrypt/key access. |
| IC-023-AC-09 | All F-05 living documents, ratified decisions, runbooks, threat model, recovery checkpoint, limitations, exact heads, and SOL evidence are complete; G1 ratification does not imply implementation acceptance or feature completion. |

**Required negative tests:** expired restore; repeated purge/rotation/recovery; actor deactivation during command; lock contention; missing/wrong/corrupt key backup; DB/key epoch mismatch; clipboard API failure; hidden-tab/unmount/stale reveal; browser back/refresh; Copilot/provider/document route probes; account deletion route absence.

**Concurrency and rollback tests:** reveal/update/delete during rotation; restore versus purge; two rotations; command interruption at every batch boundary; audit failure; key-file read failure; database disconnect/commit failure; backup manifest write failure; restore validation failure. Preserve the last fully valid key/envelope set and prove restart convergence.

**Living documentation:** one primary Markdown record per meaningful IC-023 checkpoint by default under C4, plus F-05 feature/acceptance, architecture/data-model/API, key-rotation/matched-backup runbook, browser evidence, exclusions, residual-risk, recovery-checkpoint, and exact PR/merge updates where necessary. Additional records are optional when useful; four files are not mandatory.

**SOL G2 boundary:** complete decision traceability; lifecycle and recovery failure injection; native concurrency; browser secret hygiene; full regressions; isolation; no account deletion, provider activation, external secret service, cloud, Redis, Celery, or deployment work.

## 11. Verification strategy

| Evidence area | Executable evidence required |
| --- | --- |
| Native MySQL schema | Apply from clean DB, second apply, `migrate --check`, `makemigrations --check --dry-run`, rollback/forward where safe, `SHOW CREATE TABLE`, raw-SQL check/unique/FK violation tests. SQLite is supplementary only. |
| Native concurrency | Independent DB connections plus deterministic events/barriers prove grant single-use/revoke races, revision conflicts, lifecycle/rotation/purge races, deactivation, lock order, bounded deadlock retry, and final audit/envelope cardinality. |
| Encryption | Known-answer/library interoperability where applicable; randomized round trips; nonce uniqueness sampling; bit flips in every envelope field; AAD swaps; wrong/missing/retired keys; no partial plaintext; dependency/version inspection. |
| Authorization | Full actor matrix, cross-owner list/detail/reveal/mutate/direct UUID, generic response equivalence, query-count/serialization checks, App Admin and IT-role combinations, inactive/deactivated state. |
| Grants | Password success/failure, concrete throttle/caps and concurrent limit enforcement, exact two-minute controlled clock, single use, session/user binding, replay, revoke, logout/password/deactivation, malformed session, both lock winner orders, commit barrier, post-commit response loss, and failure table. |
| Audit and rollback | Exact controlled event cardinality; injected audit write failure; DB error before/after crypto; commit failure; denial audit failure; state/grant/audit final-state assertions. |
| Secret hygiene | Unique sentinel values/keys/proofs scanned across captured logs, audit DB, error bodies, response headers except required proof, MySQL non-envelope columns, SSR/build artifacts, URLs, browser console/storage/cache, test reports and repository. Redact test command output. |
| Backup/recovery | Create current and historical matched snapshots/manifests, interrupt/restart rotation, restore each retained generation in isolation, verify all envelopes without displaying values, test DB/key/manifest mismatch and corruption permutations, and prove online-retirement/destruction guards. Never use non-test data. |
| Frontend | Vitest/Testing Library for masking, clearing, stale responses, accessibility and storage spies; `npm run typecheck`, `npm run lint`, `npm test -- --run`, `npm run build`. |
| Real browser | Authenticated owner create/list/reauth/reveal/copy/update/delete/restore; two tabs competing for a grant; expiry/revoke/deactivation; refresh/back/visibility/unmount; DevTools-equivalent storage/cache/console/network inspection; cross-owner browser/API attempt. |
| Isolation/regression | F-01–F-04 backend/frontend suites; import/route/settings inspection proving no vault key/API in Copilot, documents, workers, provider, client bundle, or unrelated commands. |

Failure injection must cover RNG/nonce failure, encrypt/decrypt/tag failure, KEK/DEK unavailability, DB read/write/commit/deadlock, audit validation/write failure, session decode/delete failure, key-backup read/write corruption, manifest mismatch, command interruption, clipboard denial, and stale frontend requests. Tests must assert what did **not** happen: no plaintext release, no partial row, no misleading success, no grant double-use, no secret-bearing diagnostic, and no invalid key retirement.

## 12. Exclusions and deferred work

- IC-024 account deletion, deletion execution, owner cascade, and audit-retention deletion.
- Sharing, delegated access, organization/team vaults, break-glass recovery, admin reveal, credential export/import, bulk operations, attachments, binary secrets, autofill, browser extensions, mobile/native clients, password generation, breach monitoring, rotation against external systems, TOTP, MFA, password reset, and account recovery.
- External credential/vault/KMS service, AWS, deployment, hosted backup, Redis, Celery, new worker infrastructure, provider activation, or private vault transfer to Copilot/AI.
- Search over encrypted values, deterministic encryption, secret fingerprints/deduplication, analytics on secret fields, and production operational execution.
- Historical “Documentation Workspaces” capabilities—owner-private Web-document workspaces, collaboration/sharing, workspace membership, ownership transfer, correction requests, and editorial review workflows—remain an unassigned product backlog. They are not F-03 as currently accepted, are not F-05, and receive no inferred Task Code or implementation authority here.

## 13. Ratified implementation decomposition and future G2 gates

| Batch | Scope | Entry / exit gate |
| --- | --- | --- |
| A — IC-021 foundations | Ratified D01–D05 and D10–D14: models, crypto/key boundary, metadata and secure CRUD services behind disabled production-sensitive routes | Separate IC-021 implementation authorization required; SOL G2 exact-head review of crypto, schema, ownership, process/key-access qualification, tamper, rollback, and native concurrency before integration |
| B — IC-022 grants | Ratified D06–D09: reauthentication, session-bound grant state machine, MySQL throttling, integration into sensitive routes, and in-memory frontend seam | Separate IC-022 implementation authorization and accepted Batch A required; SOL G2 exact-head review of proof/session/expiry/concurrency/lifecycle/browser hygiene |
| C — IC-023 lifecycle and recovery | UI completion, rotation, deletion/restore/purge, matched backup/restore, full integrated/security/browser evidence | Separate IC-023 implementation authorization and accepted Batches A/B required; SOL G2 exact-head full-feature review, then normal G3/G4/G5 gates. IC-024 remains separately gated |

Each task requires separate explicit implementation authorization before its branch or runtime work begins, one primary Markdown record per meaningful checkpoint by default under ratified clarification C4, feature-level updates where necessary, exact-head review, and separately authorized integration. Additional records are created only when they materially improve traceability. G1 ratification and this documentation PR do not create implementation branches or authorize any batch.

## 14. G1 review checklist

SOL exact-head review should verify that the 2026-11-10 ratification is accurately synchronized without changing the reviewed technical contract; every F05-D01–D15 row is RATIFIED; D11 retains no numerical audit-retention duration and blocks dependent purge; security boundaries and future G2 evidence remain intact; IC-021–IC-023 still require separate implementation authorization; and IC-024, merge, provider, infrastructure, and deployment remain excluded.

**Completion state of this document:** **PRODUCT OWNER RATIFIED — F-05 G1 COMPLETE.** Documentation synchronized for SOL exact-head review. IC-021–IC-023 implementation and PR merge remain unauthorized.
