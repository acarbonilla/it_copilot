# IC-026-T01 — Runtime and UI Alignment

**Feature:** F-07 — Local UI Alignment
**Risk:** L2 — application integration
**Baseline:** `8b9a0f3d9d71b126794ad7971575d5f7cf51c871`
**Execution date:** 2026-11-23 (Asia/Singapore)
**Task status:** **PARTIAL**

## Isolated worktree and existing runtime

The implementation was performed in the detached worktree:

`.worktrees/ic026-t01-8b9a0f3`

The worktree was created at the exact approved baseline. The legacy checkout remained on `feature/documentation-management` at `7bbb4c663a7daebe659e700dd0240556f6cc86ff` with its pre-existing tracked and untracked changes preserved.

Existing legacy services were left running and untouched:

- frontend: `http://localhost:3000`, sourced from the dirty legacy checkout;
- API: `http://127.0.0.1:8000`, existing process provenance unchanged.

Ports 3100 and 8100 were selected as safe candidates for the isolated runtime. No isolated service was started because the approved database could not be authenticated safely.

## Safe database gate

The retained disposable database name was confirmed from the accepted evidence as `it_copilot_f06_acceptance_20261123_gap02a`. A read-only Django migration-state check was attempted with the project's configured local MySQL account. Connection failed with MySQL error 1045 because the required password was not available to this process.

No credential was extracted from another process, no alternate database was substituted, and no schema, migration, fixture, session, or operational record was changed. The isolated API and Chromium workflow therefore remain **HOLD**.

## UI correction

The dashboard now uses explicit module route metadata:

- Documents → `/documents` — available;
- Copilot → `/copilot` — available;
- My Credentials → `/vault` — available;
- Private Web Documentation — unavailable with no route;
- Administration → `/admin/users` only when `is_app_admin` is true.

My Credentials is linked in both sidebar navigation and its dashboard card. Existing Copilot navigation and role-aware Administration visibility remain intact. No backend, API, authorization, session, CSRF, Vault grant, provider, or private-transfer logic changed.

## Changed files

- `apps/web/components/dashboard-shell.tsx`
- `apps/web/components/dashboard-shell.test.tsx`
- `docs/02-Development/IC-026-T01-runtime-ui-alignment.md`

## Focused verification

| Check | Result |
| --- | --- |
| Exact lockfile install | PASS — 488 packages installed; no dependency file changed |
| TypeScript | PASS |
| Focused ESLint for dashboard component/test | PASS |
| Dashboard, API client, Vault API client, Copilot, and Vault component subset | Initial run: 44 passed, 1 timed out |
| Unchanged Vault component rerun | PASS — 16/16 |
| Dashboard and CSRF/Vault API-client confirmation | PASS — 16/16 across 3 files |
| Dashboard authentication/navigation expectations | PASS within focused run |
| CSRF and Vault grant client protections | PASS within focused API-client tests |
| Provider/private-transfer configuration | Confirmed disabled in the baseline |
| Production compilation and route generation | Compiled; `/documents`, `/copilot`, and `/vault` generated |
| Production build command | HOLD — Next.js security guard rejected baseline `16.4.3` after compilation |

The single initial failure was a five-second timeout in the existing parameterized Vault API-token editor test. It was not an assertion failure; the unchanged complete Vault component file passed 16/16 on immediate focused rerun.

## Chromium verification

**NOT EXECUTED.** A safe isolated API could not be started without the authorized MySQL credential. Browser results from the legacy ports were not reused or attributed to this worktree.

Required focused browser coverage remains:

- authenticate against the isolated API;
- confirm dashboard and card navigation to Documents, Copilot, and My Credentials;
- confirm Private Web Documentation remains unavailable;
- confirm anonymous/session-expired redirects;
- exercise only authorized Vault lifecycle operations with CSRF and single-use grants;
- confirm cross-owner and logout denial;
- confirm provider/private transfer remain disabled.

## Security restrictions and findings

All accepted restrictions remain binding: owner isolation, authenticated sessions, CSRF, Vault single-use grants, no-store reveal behavior, provider/private-transfer disablement, operational Vault holds, destructive-purge HOLD, and IC-024 deferral.

The exact baseline pins Next.js `16.4.3`. Its build-time security guard recommends upgrading to a safe version. Dependency modification was prohibited by this task, so no upgrade was performed in the isolated worktree. This finding and the unavailable isolated database credential prevent a PASS runtime disposition.

## Remaining limitations and T02 readiness

The frontend integration change is ready for review based on focused unit, type, lint, and compilation evidence. **T02 is HOLD** until:

1. the isolated MySQL credential is supplied through an approved non-disclosing mechanism;
2. the exact database and no-pending-migration state are verified read-only;
3. isolated API/frontend processes are started on safe ports and exact source provenance is recorded;
4. the focused Chromium matrix passes; and
5. the Next.js security finding is separately dispositioned under an authorized dependency task.

No staging, commit, push, PR, merge, reset, clean, rebase, provider activation, operational Vault action, AWS, Redis, or deployment action occurred.

---

## IC-026-T02A - Database authorization and security-guard checkpoint

**Checkpoint date:** 2026-11-23 (Asia/Singapore)

**Baseline and runtime candidate:** `8b9a0f3d9d71b126794ad7971575d5f7cf51c871`

**Disposition:** **HOLD - DATABASE AUTHORIZATION HOLD**

This checkpoint preserves the T01 implementation and evidence above. It did not modify application source, tests, dependencies, database state, or Git history.

### Preflight and process isolation

The detached T01 worktree remains at the exact approved baseline. Its only working-tree changes are the two T01 frontend files and this living record. The dirty legacy checkout and all unrelated worktrees remain preserved.

The existing legacy frontend on port 3000 and API on port 8000 were left untouched. Candidate isolated ports 3100 and 8100 were free at preflight. No isolated API or frontend process was started.

### Absolute database authorization gate

The previously recorded candidate database is `it_copilot_f06_acceptance_20261123_gap02a`, but a database name alone is not authorization. This process has no approved, non-disclosing credential injection mechanism: the required MySQL connection variables are absent, and no ignored local environment file exists in the isolated worktree or API directory. The committed `.env.example` is documentation, not a credential source.

Consequently, this checkpoint could not independently verify:

- database identity and host;
- that the database is disposable and authorized for this task;
- least-privilege account permissions;
- existing schema and migration state; or
- safe test-data boundaries.

The earlier T01 MySQL 1045 authentication failure remains historical evidence only; it was not bypassed or retried with guessed, extracted, or alternate credentials. No database connection, migration, fixture load, schema change, session creation, or operational data action occurred.

### Chromium verification

**NOT EXECUTED.** The database authorization gate failed before dependent services could be started. The required browser matrix therefore remains unverified, including authenticated routing, anonymous and expired-session behavior, owner isolation, CSRF enforcement, Vault grant lifecycle and single-use behavior, logout denial, and disabled provider/private-data transfer.

### Next.js 16.4.3 security guard

Read-only package inspection confirms that the frontend manifest, lockfile declaration, lockfile resolution, and installed package all identify Next.js `16.4.3`; `eslint-config-next` is also pinned to `16.4.3`. No dependency file differs from the baseline.

During T01, the production build successfully compiled and generated the expected `/documents`, `/copilot`, and `/vault` routes, then exited with `SecurityFatalError`. The diagnostic stated that the installed Next.js version is affected by a known security vulnerability, strongly recommended an upgrade, and referenced the npm bulk advisory service. It did not identify a specific advisory or CVE in the captured output.

Captured diagnostic text:

```text
Error [SecurityFatalError]: Your version of Next.js is affected by a known security vulnerability.

**We strongly recommend you upgrade Next.js.**

This command stopped to show the upgrade recommendation. Retry the same command to continue the original task.
```

Classification:

- production build: **BLOCKED by the security guard after compilation**;
- isolated development or production startup: **NOT VERIFIED**;
- T02A runtime verification: **not attempted because the independent database authorization gate failed first**.

No retry-to-continue action, guard bypass, workaround, package update, lockfile rewrite, or dependency installation was performed. The dependency finding requires a separate authorized upgrade and regression task; this checkpoint makes no production-safety or production-readiness claim.

### Preserved security boundaries and next readiness

The baseline restrictions remain unchanged: authentication and owner isolation, CSRF enforcement, Vault single-use grants and no-store reveal behavior, provider/private-data transfer disabled, no operational key rotation or key retirement/destruction, no operational backup/recovery, destructive purge HOLD, and IC-024 deferred.

T02 browser verification remains **HOLD** until an authorized disposable MySQL database can be identified and validated through an approved least-privilege, non-disclosing credential mechanism. After that gate passes, the isolated API and frontend may be started on verified free ports and the focused Chromium matrix may be executed. The Next.js guard must remain separately tracked under an authorized dependency task.

---

## IC-026-SEC-02 - Next.js dependency security remediation

**Execution date:** 2026-11-23 (Asia/Singapore)

**Working SHA:** `8b9a0f3d9d71b126794ad7971575d5f7cf51c871`

**Disposition:** **PASS - LOCAL DEPENDENCY REMEDIATION**

SEC-02 updated only the two authorized direct dependency pins and the resulting lockfile. It did not change application behavior, backend code, database state, security controls, or Git history.

### Exact versions and provenance

| Package | Before | Manifest | Lockfile | Installed |
| --- | --- | --- | --- | --- |
| `next` | `16.4.3` | `16.4.6` | `16.4.6` | `16.4.6` |
| `eslint-config-next` | `16.4.3` | `16.4.6` | `16.4.6` | `16.4.6` |
| `react` | `19.3.1` | `^19.3.1` | `19.3.1` | `19.3.1` |
| `react-dom` | `19.3.1` | `^19.3.1` | `19.3.1` | `19.3.1` |

The existing npm and package-lock workflow was used with exact pins. No other direct dependency declaration changed.

### Lockfile and transitive changes

The lockfile changed only as required by the two authorized patch upgrades:

- `@next/env`: `16.4.3` to `16.4.6`;
- `@next/eslint-plugin-next`: `16.4.3` to `16.4.6`;
- Next.js optional platform SWC package records: `16.4.3` to `16.4.6` for Darwin ARM64/x64, Linux ARM64 GNU/musl, Linux x64 GNU/musl, and Windows ARM64/x64;
- registry resolution and integrity values corresponding to those packages.

The local npm operation reported five installed packages changed and 489 packages audited. React and React DOM remained unchanged.

### Focused regression evidence

| Check | Result |
| --- | --- |
| TypeScript (`tsc --noEmit`) | PASS |
| Focused ESLint across dashboard, authentication, API client, Copilot, Vault, and grant-related files | PASS - zero warnings |
| Focused Vitest set | PASS - 7 files, 51 tests |
| Dashboard/navigation | PASS within focused set |
| Authentication redirects/login and API client | PASS within focused set |
| Copilot component | PASS within focused set |
| Vault component and API client | PASS within focused set |
| CSRF and grant-related frontend behavior | PASS within focused set |

No test or application source was changed to obtain these results.

### Production build

The normal `next build` command completed successfully on Next.js `16.4.6` with exit code 0. Compilation, TypeScript validation, page-data collection, static generation, and final optimization completed. The generated route table included `/admin/users`, `/copilot`, `/dashboard`, `/documents`, `/login`, and `/vault`.

`SecurityFatalError` did not recur, and no new blocking security diagnostic was emitted. No retry, suppression, bypass flag, or security-validation modification was used. A successful local build is not a production-readiness or deployment approval.

### Remaining dependency findings

The read-only npm audit reports seven moderate findings and no low, high, or critical findings. These are transitive development-tooling findings rooted in `minimatch` through the TypeScript ESLint dependency chain (`@typescript-eslint/eslint-plugin`, parser, type-utils, typescript-estree, utils, and `typescript-eslint`). The underlying advisory is `GHSA-g3hv-75wg-m249`, affecting the nested `minimatch` range used by that tooling.

No automatic audit fix or unrelated dependency upgrade was performed. These residual development-tooling findings require separate scope if remediation is desired.

### Retained restrictions and remaining hold

Authentication, CSRF, Vault grants, owner isolation, provider/private-data-transfer disablement, operational Vault restrictions, destructive-purge HOLD, and IC-024 deferral remain unchanged. No database was accessed, no service was started, and no provider, AWS, Redis, deployment, or operational Vault action occurred.

Database authorization and focused Chromium runtime verification remain **HOLD** under the T02A gate. SEC-02 resolves the previously confirmed Next.js production-build security guard only; it does not complete F-07 or authorize publication.

---

## IC-026-T02B - Database access and runtime-readiness checkpoint

**Execution date:** 2026-11-23 (Asia/Singapore)

**Working SHA:** `8b9a0f3d9d71b126794ad7971575d5f7cf51c871`

**Disposition:** **HOLD - DATABASE AUTHORIZATION HOLD**

T02B stopped at the mandatory MySQL authorization gate. No database connection, isolated application service, or Chromium session was started.

### Preflight identity

The isolated worktree retained exactly the five expected IC-026 changes: the dashboard component and test, the authorized Next.js manifest and lockfile update, and this living record. All unrelated worktrees and processes were preserved.

At inspection time, ports 3000, 8000, 3100, 8100, and 3306 had no TCP listener. The Windows `MySQL80` service reported `Running` with automatic startup, but service state alone did not establish a usable local-only TCP endpoint or authorize a connection.

### Authorization and credential gate

Historical evidence records `it_copilot_f06_acceptance_20261123_gap02a` as a retained disposable F-06 database with an existing application schema and synthetic evidence. T02B explicitly states that this history is not permission to reuse the database. No current PO/SOL record expressly authorizes that database, or another named database, for F-07 testing.

No approved credential mechanism was available to this process:

- `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, and `MYSQL_PORT` were absent;
- required runtime secret variables were also absent; and
- no ignored `.env` or `.env.local` file existed at the worktree root or under the API or frontend directories.

No password, connection string, or secret value was inspected, extracted, displayed, stored, or documented. No alternate account or database was attempted.

### Required administrator and governance actions

Before a later runtime-verification task can proceed:

1. PO/SOL must expressly authorize a specific named disposable database for F-07 testing, including whether the retained F-06 database may be reused.
2. A database administrator must confirm that the selected database is local-only, test-only, contains no production or personal records, and already has the complete application schema.
3. The administrator must provide an existing least-privilege account scoped to that database through an approved ignored environment file or secure environment injection. T02B did not authorize creation of users, grants, or authentication changes.
4. The administrator must confirm the intended local MySQL connection endpoint because the service was running but no TCP listener was observed on port 3306.
5. Runtime application secrets required by the isolated API and Vault checks must be supplied through the same approved non-disclosing mechanism.

### Verification not executed

Database identity, privilege scope, schema tables, migration readiness, and test-data boundaries remain **NOT VERIFIED** for T02B. The API and frontend were not started, so ports 8100 and 3100 were not assigned to serving processes. Chromium authentication, dashboard navigation, Documents, Copilot, Vault, CSRF, single-use grants, no-store reveal, cross-owner denial, logout denial, Private Web Documentation deferral, and administrator visibility remain **NOT EXECUTED** in this checkpoint.

The corrected dashboard and Next.js `16.4.6` evidence from earlier IC-026 tasks remains preserved but was not substituted for new runtime verification. Provider/private-data transfer remained disabled, and no operational Vault, purge, IC-024, AWS, Redis, deployment, migration, dependency, application-source, or Git publication action occurred.

F-07 runtime readiness remains **HOLD** pending the explicit authorization and administrator-provisioned secure access described above.

---

## IC-026-ENV-03 - MySQL loopback-hardening checkpoint

**Execution date:** 2026-11-23 (Asia/Singapore)

**Disposition:** **HOLD - ADMINISTRATOR BACKUP PREREQUISITE**

ENV-03 confirmed the `MySQL80` service identity and effective configuration path. The service was running from MySQL Community Server 8.0.37 with `C:\ProgramData\MySQL\MySQL Server 8.0\my.ini`. At the pre-change observation point there were no active MySQL client connections and no application listeners on ports 3000, 8000, 3100, or 8100. No known active workload was therefore identified, but this observation does not replace administrator confirmation that no approved remote client depends on the service.

The effective `[mysqld]` configuration contained ports 3306 and 33060 without existing `bind-address` or `mysqlx-bind-address` directives. The original listeners remained `0.0.0.0:3306` and `0.0.0.0:33060`.

### Backup gate result

An access-restricted administrator-controlled directory was created at:

`C:\ProgramData\MySQL\MySQL Server 8.0\ConfigBackups`

The attempted timestamped backup `my.ini.backup-20261123-ic026-env03` was not created because the executing process did not receive an OS administrator token and Windows denied the copy into that restricted directory. No configuration content was copied or exposed.

Because the mandatory readable backup could not be completed, ENV-03 stopped before editing `my.ini`. No binding directive changed, no validation or service restart occurred, and rollback was not required. Post-stop verification confirmed that the original configuration timestamp and length were unchanged, `MySQL80` remained running, and both original all-interface listeners remained in place.

### Required administrator continuation

An interactive elevated administrator must:

1. create and verify the timestamped ACL-preserving backup in the existing restricted backup directory;
2. confirm no approved remote MySQL client requires access;
3. add only `bind-address=127.0.0.1` and, because X Protocol is enabled, `mysqlx-bind-address=127.0.0.1` under `[mysqld]` without duplicate directives;
4. validate the configuration using installed MySQL-supported mechanisms;
5. restart `MySQL80` once with rollback to the verified backup if startup fails; and
6. confirm that ports 3306 and 33060 listen only on IPv4 loopback with no wildcard, non-loopback, or externally reachable IPv6 listener.

Windows Firewall remained unchanged. The earlier finding that Public and Private firewall profiles were disabled remains open. ENV-04 is **NOT READY** until the elevated administrator operation completes and loopback-only listeners are independently verified.

---

## IC-026-ENV-04 - Controlled environment readiness

**Execution date:** 2026-11-24 (Asia/Singapore)

**Working SHA:** `8b9a0f3d9d71b126794ad7971575d5f7cf51c871`

**Disposition:** **HOLD - ENVIRONMENT AND SECRET PROVISIONING REQUIRED**

ENV-04 performed only read-only host, repository, configuration, and credential-presence checks. It did not connect to MySQL, inspect application records or secret values, modify schema or data, run migrations, start the API or frontend, launch Chromium, or change Git history.

### Worktree and MySQL endpoint gate

The detached IC-026 worktree remains at the exact approved baseline. Its existing expected changes are preserved: the dashboard component and test, the authorized Next.js `16.4.6` manifest and lockfile update, and this living record. Unrelated worktrees and the dirty legacy checkout were not modified.

`MySQL80` reported `Running` with automatic startup. The effective configuration file contains `bind-address=127.0.0.1` and `mysqlx-bind-address=127.0.0.1`, consistent with the intended loopback-only configuration. However, independent checks using the Windows TCP connection table and `netstat` found no listener on either `127.0.0.1:3306` or `127.0.0.1:33060`, and no wildcard or non-loopback listener on those ports.

Therefore the required effective endpoint was not available. This is not an external-listener security hold, but it is an environment-readiness failure. No database authentication was attempted.

### Authorized database and account readiness

The task authorization names `it_copilot_f06_acceptance_20261123_gap02a` as the sole candidate for suitability assessment. Exact server-side identity, test-only/disposable classification, absence of production or personal data, application-schema presence, migration history, and migration readiness could not be independently confirmed because the endpoint and approved account prerequisites were unavailable.

No process environment values were present for `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, or `MYSQL_PORT`. No ignored `.env` or `.env.local` file existed at the isolated worktree root, `apps/api`, or `apps/web`. Consequently, the existence and grant scope of a database-scoped runtime account remain unverified. No password was searched for in unrelated files, guessed, reset, displayed, or recovered, and no user or grant change occurred.

An administrator must provide an existing account restricted to the named test database, with no global or production-database privileges and only the permissions required by the local MVP runtime. After the listener is restored, a later authorized read-only check must confirm `CURRENT_USER()`, the selected database, grants, expected Django tables, applied migration records, and the absence of pending required migrations without changing schema or records.

### Runtime-secret readiness

No authorized process environment values were present for `DJANGO_SECRET_KEY`, `VAULT_KEK_BASE64`, `VAULT_KEK_FILE`, `VAULT_KEK_PROVIDER_FILE`, or `VAULT_GRANT_PEPPER`. The committed Django fallback and test-only defaults are not accepted runtime credentials. Because no local secret file exists, file ACLs and Vault test-key provenance could not be validated.

The repository ignores `.env` and `.env.*` files at the worktree root and below application directories. Only `.env.example` and the generated frontend `next-env.d.ts` are tracked among environment-named files. A focused source scan found no frontend `NEXT_PUBLIC_` variable referencing Django, MySQL, Vault, KEK, pepper, password, database, or other server-secret names. This confirms a safe ignored-file mechanism is available, but not that credentials have been provisioned.

An administrator must securely inject a development-only Django secret and authorized test-only Vault KEK configuration plus `VAULT_GRANT_PEPPER`, using an ignored local environment file with user-restricted filesystem permissions or an approved process-injection mechanism. The administrator must attest that the Vault material belongs to the retained synthetic records, has known test provenance, and is not reused operationally. Values must not be committed, logged, documented, or returned in task evidence.

### Provider/private-transfer and readiness decision

The retained baseline configuration keeps provider use and private transfer disabled. No provider, private-transfer, operational Vault, purge, IC-024, AWS, Redis, deployment, or application-runtime action occurred.

F-07 runtime readiness remains **HOLD**. Before a separately authorized runtime task, an administrator must:

1. restore and verify effective IPv4 loopback listeners on `127.0.0.1:3306` and `127.0.0.1:33060`, with no wildcard, non-loopback, or externally reachable IPv6 listener;
2. independently attest the named database is disposable/test-only and contains no production or personal data;
3. securely provide the existing least-privilege database-scoped account;
4. securely provide the development-only Django secret and provenance-confirmed test-only Vault KEK and grant pepper; and
5. permit a later read-only database identity, grant, schema, and migration verification.

The API, frontend, and Chromium must remain stopped until SOL reviews this evidence and the Product Owner separately authorizes runtime execution.

---

## IC-026-ENV-04B - Controlled credential readiness

**Execution date:** 2026-11-24 (Asia/Singapore)

**Working SHA:** `8b9a0f3d9d71b126794ad7971575d5f7cf51c871`

**Disposition:** **HOLD - CREDENTIAL AND RUNTIME-SECRET PROVISIONING REQUIRED**

ENV-04B accepted the task brief's verified MySQL loopback prerequisites and rechecked the service state. `MySQL80` remained `Running`, so the listener checks were not repeated. No application service or browser was started.

### Database access and classification

The sole authorized candidate remains `it_copilot_f06_acceptance_20261123_gap02a`. No approved database credential handoff was available in the isolated worktree or process environment. Therefore no MySQL connection was attempted, and exact server-side identity, disposable/test-only provenance, absence of production or personal records, existing application tables, Django migration history, pending-migration state, and compatibility with the retained application remain unverified in this checkpoint.

No database contents, private documents, Vault plaintext, schema, migration, or record were inspected or changed. Historical F-06 evidence was not treated as an independent current classification.

### Account and credential-delivery readiness

No process environment values were present for `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, or `MYSQL_PORT`. No `.env` or `.env.local` file existed at the worktree root, `apps/api`, or `apps/web`. As a result, no existing database-scoped account could be identified or its localhost restriction, database scope, global privileges, production-database exclusions, or runtime permissions verified.

Repository ignore rules already exclude `.env` and `.env.*` at the approved locations. A focused scan found no server-secret-like `NEXT_PUBLIC_` references. This establishes an available non-disclosing handoff pattern, but no file was created or populated and no credential value was read, printed, logged, documented, or committed. File-permission scope remains not applicable until an administrator provisions an approved file.

### Django and Vault secret readiness

No authorized process values were present for `DJANGO_SECRET_KEY`, `VAULT_KEK_BASE64`, `VAULT_KEK_FILE`, `VAULT_KEK_PROVIDER_FILE`, or `VAULT_GRANT_PEPPER`, and no approved local environment file supplied them. The committed Django fallback is not accepted as a runtime credential.

Django secret readiness is therefore **SECRET HOLD**. Vault readiness is **VAULT SECRET HOLD** because neither test-key availability nor provenance and correspondence with retained synthetic Vault records can be confirmed. No Vault key was generated, replaced, rotated, recovered, exported, or inspected.

### Remaining prerequisites and recommendation

An administrator must:

1. provide an existing localhost database account scoped only to `it_copilot_f06_acceptance_20261123_gap02a`, without global administrative or production-database privileges;
2. deliver the account through an ignored local file with user-restricted ACLs or approved process injection;
3. independently attest that the database is disposable/test-only and contains no production or personal data;
4. provide a development-only `DJANGO_SECRET_KEY` through the same approved non-disclosing mechanism; and
5. provide provenance-confirmed test-only Vault KEK configuration and `VAULT_GRANT_PEPPER` corresponding to any retained synthetic Vault records.

Only after those prerequisites are available may a later authorized task perform read-only selected-database, grant, schema, and migration checks. Provider use and private transfer remain disabled in the retained baseline.

F-07 runtime readiness remains **HOLD**. The corrected dashboard and Next.js `16.4.6` changes remain preserved. No database/user/grant, schema/data, migration, dependency, application-source, provider, Vault, purge, IC-024, AWS, Redis, deployment, Git publication, API/frontend startup, or Chromium action occurred. SOL review and separate Product Owner authorization remain mandatory before application startup.

---

## IC-026-ENV-05 - Disposable F-07 environment provisioning checkpoint

**Execution date:** 2026-11-25 (Asia/Singapore)

**Working SHA:** `8b9a0f3d9d71b126794ad7971575d5f7cf51c871`

**Disposition:** **HOLD - ADMINISTRATOR CREDENTIAL HOLD**

### Administrator authorization and MySQL endpoint

The controlled host session ran as the authorized local principal. `MySQL80` was `Running` with automatic startup. Classic MySQL was listening only on `127.0.0.1:3306`; no wildcard or non-loopback listener on port 3306 was present. The MySQL 8.0.37 client was available from the installed MySQL Server 8.0 distribution.

The administrator principal had no MySQL login-store entry, and no other approved non-disclosing authentication mechanism was available. In accordance with the task stop condition, no password was guessed, recovered, reset, displayed, or searched for in unrelated files, and no database connection or privileged SQL was attempted.

### Disposable database and account scope

The authorized identifier is `it_copilot_f07_devtest`. Because administrator database authentication was unavailable, its server-side absence, record count, test-only designation, and lack of production dependencies could not be established. The database was not created, altered, dropped, truncated, or reused. The retained F-06 database and all existing databases and records were left untouched.

No dedicated localhost-only account was created and no grant was issued or changed. Required future scope remains limited to `it_copilot_f07_devtest` with only application workflow privileges, no remote-host login, and no `SUPER`, `FILE`, `PROCESS`, `GRANT OPTION`, or other global privilege. Effective grants remain unverified.

### Secret delivery, test-key provenance, and ACL hygiene

The approved application contract loads server-only local values from the repository-root `.env`. Git ignore rules were confirmed to exclude that path, and no server-secret-like `NEXT_PUBLIC_` injection was identified. No `.env` existed at the checkpoint, so no ACL was applicable and no credential or secret file was created.

The application requires a base64-encoded 256-bit Vault KEK and a `VAULT_GRANT_PEPPER` of at least 32 bytes. Because the mandatory administrator authentication prerequisite was not satisfied, no Django secret, Vault KEK, pepper, or database password was generated or delivered. No operational or retained F-05/F-06 key material was read, reused, recovered, rotated, exported, or replaced.

### Schema readiness, security findings, and remaining prerequisites

Schema readiness is **NOT ASSESSED** because `it_copilot_f07_devtest` was not created. If a later authorized provisioning task creates it, its initial state must be reported as **SCHEMA NOT INITIALIZED** and Django migrations must remain subject to a separate minimal authorization; ENV-05 does not authorize migrations.

The existing IC-026 dashboard changes and Next.js `16.4.6` dependency changes remain preserved. Provider use and private transfer remain disabled in the baseline. Session authentication, CSRF controls, owner isolation, Vault grant behavior, no-store reveal behavior, accepted limitations and decisions, operational Vault holds, destructive-purge hold, and the IC-024 deferral were not changed.

Before provisioning can resume, an administrator must authenticate to MySQL through an approved interactive or non-disclosing mechanism. A later controlled task must then confirm the database-name conflict check and provenance, create the database only if absent, create and verify the dedicated scoped account, generate and securely inject fresh development/test-only secrets with user-restricted ACLs, and report the fresh database as schema-not-initialized. No application, API, frontend, or Chromium testing may start automatically.

## IC-026-ENV-05-R1 — Persistent local development checkpoint

**HOLD — administrator MySQL authentication required.** R1 supersedes the disposable database plan and selects `it_copilot_dev` for persistent local development. MySQL80 was running, TCP connectivity to `127.0.0.1:3306` succeeded, and the observed MySQL process listened only on loopback ports 3306 and 33060. The host session had no MySQL login store and the worktree root had no local `.env`.

Database existence, ownership, provenance, schema and account grants remain unverified. This checkpoint performed no database creation or reuse, migration, synthetic data seeding, or secret provisioning. Windows ACL verification is pending creation of an approved configuration file. The previously verified server-only loading contract supports the Git-ignored root `.env`, a base64-encoded 32-byte Vault KEK, and a grant pepper of at least 32 bytes. Persist development-only key material for future sessions.

The isolated worktree was verified at `8b9a0f3d9d71b126794ad7971575d5f7cf51c871` with the existing dashboard and dependency edits and installed Next.js `16.4.6`. The planned endpoints are API `http://127.0.0.1:8100` and frontend `http://localhost:3100`. Existing settings use `FRONTEND_ORIGIN` for both CORS and CSRF. Set it to the frontend URL and point `NEXT_PUBLIC_API_BASE_URL` to the API URL. Effective configuration and startup readiness are pending. Provider and private transfer remain disabled.

Resume after an administrator authenticates locally through an approved method. Verify database provenance and least-privilege grants before applying R1-authorized committed migrations to the exact target. Manual Chromium acceptance remains on hold pending environment readiness, SOL review, and a separate Product Owner decision.

## IC-026-ENV-05-R1-COMPLETE — Administrator handoff

**ADMINISTRATOR AUTHENTICATION HOLD.** The isolated detached checkout `.worktrees/ic026-env05-r1-complete` was created from verified `origin/main` at `2dff0dbd499592428aa3a7c6ebfa5dfcc716b275`. The merged dashboard routes and lockfile versions were confirmed. MySQL80 was running, TCP port 3306 was reachable, and both observed MySQL listeners were loopback-only. The host session had no MySQL login store and no authenticated administrator session was available to this task.

The administrator must use an approved local password prompt or Workbench session to check `it_copilot_dev` and the dedicated account before provisioning. The project's database settings are `utf8mb4` and `utf8mb4_unicode_ci`. If the database exists, establish development-only provenance before any write. The proposed account is `it_copilot_dev_app@localhost`, scoped to the exact schema with Django runtime and migration privileges. Ownership, existence, grants, and migration state await authenticated verification.

The planned endpoints are MySQL `127.0.0.1:3306`, API `http://127.0.0.1:8100`, and frontend `http://localhost:3100`. The frontend origin can be set through the existing CORS and CSRF configuration. Provider use and private transfer are disabled in the merged settings. Credential injection, ACL validation, Django and Vault secret generation, migrations, and synthetic data setup are pending. Manual testing readiness remains on hold.

## IC-026-ENV-05-R2 — Credential reuse preflight

The isolated detached checkout and local `origin/main` reference both resolve to `2dff0dbd499592428aa3a7c6ebfa5dfcc716b275`. The Product Owner confirmed administrator access. The directory containing the explicitly authorized development `.env` is still required before inspecting configuration or authenticating with its credentials.

Credential reuse remains unassessed. Database existence, account identity and grants, Git ignore coverage, Windows ACLs, and Django and Vault secret presence and provenance are unverified. This checkpoint made no database changes. Manual testing readiness remains on hold.

### R2 follow-up — Credential file access

The repository-root `.env` exists, is Git-ignored, and is absent from the Git index. Its Windows ACL inherits Modify permissions for a sandbox group and two additional security identifiers. It therefore fails the intended-principal-only access requirement. Credential reuse is unsuitable under the current ACL. The file contents were left unopened, so database existence, account grants, and Django and Vault secret presence and provenance remain unverified. Manual testing readiness is on hold pending correction of file access and credential verification.

### R2 continuation — Authorized configuration verification

The Product Owner explicitly authorized inspection of the repository-root `.env`. Git ignore and the inherited Windows permissions finding were reconfirmed. The configured endpoint is `127.0.0.1:3306` and the configured database is `my_database`. The target mismatch triggered the stop condition before MySQL authentication. The existence of `it_copilot_dev` and account grants remain unverified. The existing file is unsuitable for reuse as configured.

The Django secret setting is populated and its development provenance is unverified. None of the recognized Vault KEK settings or the grant pepper was populated in this file. Vault secret readiness is **VAULT SECRET HOLD**. No secret values were recorded, and manual testing readiness remains on hold.

## IC-026-ENV-05-R3 — Account verification checkpoint

The Product Owner approved R3. Django can load a separate Git-ignored `.env` from the isolated checkout root or accept per-process environment variables. The configured account authenticated over Classic TCP at `127.0.0.1:3306` without selecting a default schema. Its own grant report included a global privilege entry, so it is unsuitable as the dedicated development runtime account. The target was not visible in the session metadata. This does not establish server-wide absence.

No approved administrator login path was available in the host session. Administrator verification of target existence and provenance and creation or verification of a dedicated account remain on hold. No runtime configuration, ACL change, secret generation, schema change, migration, seeding, or service startup occurred.

## IC-026-DEV-01 — Existing database safety checkpoint

The temporary development exception authorized reusing the existing account without changing grants. The isolated checkout remained at `2dff0dbd499592428aa3a7c6ebfa5dfcc716b275`. A read-only connection confirmed `my_database` at `127.0.0.1:3306`. Schema metadata indicated existing user, session, and security-audit data. Development-only provenance could not be established. Prior project evidence identifies this as the configured database left untouched during separate acceptance work. No user, session, audit, or application record contents were retrieved.

Comparison to the migration ledger found 16 committed project migrations absent across Copilot, Documents, Security Audit, and Vault. No Vault tables were listed. Database classification triggered the stop condition before runtime configuration, secret provisioning, migrations, startup, or browser testing. An administrator or Product Owner must establish that existing records are development-only and free of sensitive data, or designate a verified safe development database.

## IC-026-DEV-02B — Django Development Initialization

The isolated checkout is at `2dff0dbd499592428aa3a7c6ebfa5dfcc716b275`. The merged Documents, Copilot, and Vault routes and the Next.js and ESLint config pins at 16.4.6 were verified. The approved local MySQL account selected `it_copilot_dev` at `127.0.0.1:3306`. The schema used `utf8mb4` and `utf8mb4_unicode_ci` and had zero tables before initialization. The temporary development exception covered the account's existing global grants.

Django loaded the isolated worktree's ignored root `.env`. Fresh development-only Django secret, 32-byte Vault KEK, and grant pepper were generated and verified through the runtime settings and key loader. The backend config and separate synthetic login file have explicit ACLs for the intended development principal and SYSTEM. Both files are ignored and untracked. The legacy root configuration was preserved.

The reviewed migration plan covered Accounts, Auth, Content Types, Copilot, Documents, Security Audit, Sessions, and Vault. All 48 migrations applied to the development schema. Zero migrations remain. The dry-run migration drift check and the database-aware Django system check passed. One active, non-admin synthetic IT member was created through the Django user manager and verified with Django authentication. Its password is stored only in the protected local login file. No other test records were imported or seeded.

The configured endpoints are API `http://127.0.0.1:8100` and frontend `http://localhost:3100`. Django CORS and CSRF trust the requested frontend origin and the ignored frontend override points at the API. Provider and private transfer are disabled. The isolated frontend has no local dependency installation. Browser testing also needs to check session and CSRF cookies because the requested endpoints use different site names with existing SameSite=Lax settings. No API, frontend, or browser was started. Backend initialization is complete. Manual browser readiness remains pending local frontend dependency installation and startup verification.

## IC-026-T02C — Manual Runtime Verification

The isolated checkout `.worktrees/ic026-env05-r1-complete` ran at `2dff0dbd499592428aa3a7c6ebfa5dfcc716b275`. Django verified `it_copilot_dev`, 48 applied migrations, zero pending migrations, the synthetic login, both development Vault settings, and disabled provider/private transfer before startup. Django ran on `http://127.0.0.1:8100` and Next.js ran on `http://127.0.0.1:3100`. Process configuration aligned the CORS and CSRF frontend origin with the browser URL. Both listeners were loopback-only. No cookie or security settings changed.

`npm ci` completed from the committed lockfile using Node 24.13.0 and npm 10.8.2. Installed Next.js and eslint-config-next were 16.4.6. React and React DOM were 19.3.1. Next.js compiled the exercised routes. The API returned HTTP 200 for the CSRF bootstrap, login, and authenticated identity.

| Chromium check | Result |
| --- | --- |
| Anonymous, login, reload, logout | Passed. Protected routes redirected after logout and after simulated loss of the session cookie. Actual server-side expiration was not exercised. |
| Dashboard | Passed. Documents, Copilot, and My Credentials linked to their routes. Private Web Documentation was unavailable and Administration was hidden for the member. |
| Documents | Authenticated route and empty state passed. Upload and cross-owner behavior were not exercised. |
| Copilot | Authenticated route passed. A synthetic query with no authorized source returned the insufficient-documentation response. Positive citation rendering requires an eligible fixture. |
| My Credentials | Authenticated route, synthetic creation, reauthenticated reveal with no-store, and rejection of the same grant-bearing request on replay passed. A synthetic record was retained. |
| Security | Missing-CSRF logout and non-admin users API requests returned 403. No uncaught page exceptions or external browser requests appeared. The primary run counted seven console errors. A focused denial run counted four console errors and captured two 401s and one 403. Console messages were not retained. |

Disposition is **PARTIAL**. The core loopback runtime works with the approved synthetic login. Cross-owner denial, actual expiration, document processing, and positive Copilot citations remain unverified. No second synthetic identity was created. No operational or final F-07 acceptance is implied.

## IC-026-T02D — Remaining Chromium coverage

The existing isolated frontend and Django API returned HTTP 200 at their loopback endpoints on ports 3100 and 8100. The checkout remained at `2dff0dbd499592428aa3a7c6ebfa5dfcc716b275`. Django preflight confirmed `it_copilot_dev`, 48 applied migrations, zero pending migrations, successful development key loading, and provider/private transfer disabled. The Owner and Member 2 aliases refer to separate synthetic non-admin accounts. The new Member 2 credential was stored in a Git-ignored file with access restricted to the development principal and SYSTEM.

| Check | Evidence |
| --- | --- |
| Document upload and processing | Owner uploaded one synthetic TXT through the browser with HTTP 201. The document worker succeeded and the UI API reported `ready`. The retrieval job succeeded on its first attempt and published one searchable chunk. |
| Positive Copilot citation | The first browser wait timed out, but the persisted grounding state was `REFERENCES` and native retrieval produced one owner match. A focused browser retry confirmed the authorized reference list showed the exact synthetic document title and Version 1. AI-generated synthesis stayed disabled. |
| Cross-owner isolation | Member 2's lists excluded the Owner's document and Vault record. Document detail, download, and Vault detail each returned 404 without the corresponding synthetic label in the denial body. Member 2 asked the same Copilot question and received the insufficient-documentation response without the Owner citation. |
| Actual session expiration | After verifying ownership of Member 2's current test session, only that session row's expiration timestamp was moved into the past. Chromium retained the cookie, Django returned 401 on the identity endpoint, and Documents redirected to login. Global policy was unchanged. |
| Console triage | Relevant T02C 401/403 requests were identifiable in the Django logs, including anonymous identity, grant replay, and missing CSRF. T02D reproduced expected 401s after expiry and 404s for owner isolation. A focused Chromium diagnostic identified the login resource 404 as `/favicon.ico`. The original seven console messages were not retained individually, so an exact attribution is unavailable. No uncaught page exceptions or external browser requests were observed during the tested workflows. |

Remaining operational limitations and HOLDs are unchanged. The append completes the requested manual runtime coverage for Product Owner and SOL review. The missing favicon is a nonblocking cosmetic issue, and the initial citation wait timeout cleared on a focused retry. This checkpoint does not declare final F-07 acceptance.

## IC-026-T02E — Dashboard origin investigation

The Product Owner reported a legacy-looking dashboard. The exact URL and browser context used for that inspection were unavailable. The fresh investigation found no listener on port 3000. Port 3100 was served by the existing Node/Next.js process linked by its command line and parent chain to the isolated worktree, with Next.js 16.4.6 and source SHA `2dff0dbd499592428aa3a7c6ebfa5dfcc716b275`. Port 8000 responded from the separate Python `manage.py runserver` process associated with the legacy repository. Its exact working directory, loaded source SHA, and database were not independently established. Port 8100 was served by the Python `runserver 127.0.0.1:8100 --noreload` process whose launch chain includes the isolated worktree. This is the existing runtime previously verified against `it_copilot_dev`.

Fresh Chromium opened `http://127.0.0.1:3100/dashboard`, followed the anonymous login redirect, and authenticated with the synthetic member. The dashboard showed Documents, Copilot, and My Credentials as Available and linked to `/documents`, `/copilot`, and `/vault`. All three links navigated successfully and the authenticated identity endpoint returned HTTP 200 on each page. Private Web Documentation was unavailable and unlinked. Administration was hidden. Browser requests used only the approved frontend and API origins. The run recorded two expected anonymous identity 401s and one resource 404 consistent with the previously reproduced missing favicon. No uncaught page exception occurred.

The approved runtime served the corrected dashboard, so no restart or other runtime correction was needed. The Product Owner's earlier view was not reproduced. A different origin or prior browser state remains possible, and root cause cannot be assigned without the original URL or a fresh reproduction. The verified inspection URL is `http://127.0.0.1:3100/dashboard`. Final F-07 acceptance remains pending.

## IC-026-T03 — Main runtime transition HOLD

The primary checkout remains on `feature/documentation-management` at `7bbb4c663a7daebe659e700dd0240556f6cc86ff` with tracked edits and untracked files. The local `origin/main` ref and the isolated detached HEAD both resolve to approved SHA `2dff0dbd499592428aa3a7c6ebfa5dfcc716b275`. The approved tree includes the Dashboard, Documents, Copilot, and Vault routes and pins Next.js 16.4.6. Dashboard source marks Private Web Documentation unavailable and gates Administration on the admin flag.

The existing runtime remains in `.worktrees/ic026-env05-r1-complete`. Next.js listener PID `14380` descends from launcher `19208`, whose command line points to that worktree. Django listener PID `18692` descends from launcher `16084`, started with the worktree's API directory as its working directory. Both run under the local development account. The existing URLs are `http://localhost:3001` and `http://localhost:8001`. The launch used process-local overrides for the frontend origin and API URL. A read-only Django connection confirmed `it_copilot_dev` at `127.0.0.1:3306`. Git ignores both runtime config files. The backend `.env` grants explicit access to the development account and SYSTEM. The frontend `.env.local` inherits its directory ACLs.

No process handoff or main-directory browser verification was performed. Login, module navigation, session refresh, logout, and provider/private-transfer traffic checks for the replacement runtime remain pending. Use a separate clean Git worktree pinned to the approved SHA for the replacement runtime at `http://127.0.0.1:3100` and `http://127.0.0.1:8100`. This checkpoint does not constitute F-07 acceptance.

## IC-026-T03A — Permanent main runtime handoff

With PO approval, the sibling worktree `../it_copilot_main_runtime` was created at detached SHA `2dff0dbd499592428aa3a7c6ebfa5dfcc716b275`. Local `main` pointed at a different commit. The primary checkout stayed on its dirty feature branch. `npm ci` completed using the committed lockfile and installed Next.js 16.4.6. Next.js regenerated its tracked `next-env.d.ts` to point to development type output.

Next.js listens at `http://127.0.0.1:3100` (listener `19100`, launcher `11248`). Django listens at `http://127.0.0.1:8100` (listener `19968`, launcher `19916`). The launch working directories were the sibling worktree's web and API directories. Django's system check passed and a read-only query confirmed `it_copilot_dev` at `127.0.0.1:3306`. An allowlisted transfer preserved the development database and Vault settings. Both ignored config files have explicit access for the development account and SYSTEM. Private transfer was verified disabled and provider enablement is hard-coded false in the approved settings.

Chromium passed synthetic login, Dashboard, all three available module links, unavailable Private Web Documentation, hidden non-admin Administration, session refresh, logout, and protected-route redirect. It recorded 27 successful calls to the replacement API, zero external browser requests, and zero page exceptions. The isolated server trees were retired after verification. The legacy listeners on ports 3000 and 8000 remained present. Focused runtime handoff passed. Final F-07 acceptance remains with the PO.

## IC-026-T04 — Copilot runtime diagnosis

The permanent checkout at `../it_copilot_main_runtime` was at `2dff0dbd499592428aa3a7c6ebfa5dfcc716b275`. Frontend listener `19100` and API listener `19968` matched the T03A process trees at ports 3100 and 8100. Django selected `it_copilot_dev`, with 48 applied migrations and zero pending. Provider and private transfer were disabled. No worker process was observed. One processing job was pending and no index jobs were active. The diagnostic did not start a worker.

The approved synthetic owner’s `F07 T02D Heliox Nebula`, Version 1, was ready. Its published MySQL full-text generation matched the current version and had one searchable chunk. The matching index job succeeded on its first attempt.

Reproduce by signing in as the approved synthetic owner at `http://127.0.0.1:3100`, opening Copilot, creating a conversation, and submitting these questions in order:

| Question | Expected | Observed |
| --- | --- | --- |
| What is the Heliox Nebula calibration code? | Reference-only result citing the synthetic title and Version 1 | One MySQL lexical candidate. HTTP 201 in 1,953 ms with `assistant_message.grounding_status=insufficient`, `provider_status=disabled`, and zero citations. No title or version reached the browser. |
| What is the migratory range of the Andean flamingo? | Insufficient authorized documentation and zero citations | Zero MySQL lexical candidates. HTTP 201 in 86 ms with `assistant_message.grounding_status=insufficient`, `provider_status=disabled`, and zero citations. |

Both response envelopes contained `conversation`, `user_message`, and `assistant_message`. The initial browser assertion was ambiguous because both turns rendered the same fallback. A follow-up Chromium run reopened the saved conversation and counted two fallback panels and zero reference lists. There were zero HTTP errors, external browser requests, or page exceptions in the submission run.

Classification is API response behavior caused by local artifact-store configuration. The permanent runtime’s private storage root lacked both the original and extracted files for the synthetic version. Both files were present and passed integrity checks under the isolated worktree’s storage root. The evidence authorization step requires both files and drops the indexed candidate when integrity validation cannot find them. The positive result therefore failed before frontend rendering. The negative fallback behaved as expected.

Request separate approval to align the permanent runtime with the approved protected development artifact store and then rerun both browser checks. No runtime configuration, application code, migrations, or artifact files were changed. The synthetic diagnostic conversation remains in the development database. The PO’s original wording was unavailable, so the two reported failures cannot be correlated exactly. Final F-07 acceptance remains pending.

## IC-026-T05 — Protected development artifact store

With PO approval, the permanent runtime at `2dff0dbd499592428aa3a7c6ebfa5dfcc716b275` was configured through its ignored `.env` to use `C:/Users/dc/PycharmProjects/it_copilot_dev_artifacts`. Preflight confirmed `it_copilot_dev`, zero pending migrations, and disabled provider and private transfer. The application provisioned the root and verified its restrictive Windows ACL for the development principal and SYSTEM. The runtime config ACL was preserved.

Only the approved synthetic owner’s current Version 1 original and extracted artifacts were copied from the isolated store under their existing relative storage keys. Source and destination passed the application’s byte-length and SHA-256 checks. The source files were retained. Database paths, schema, and application code were unchanged. This is a synthetic-only handoff; other artifact records were outside scope.

Django alone was restarted from the permanent API directory, with launcher `20012` and listener `14760` on port 8100. The permanent frontend listener remained `19100` on port 3100. Chromium opened Documents and downloaded the approved fixture with HTTP 200. The calibration-code question returned HTTP 201 with one citation and rendered the correct title and Version 1. The flamingo question returned HTTP 201 with zero citations and rendered the insufficient-documentation fallback. Both responses reported the provider disabled. Chromium recorded zero external requests and zero uncaught page errors. The diagnostic conversation was retained. Focused verification passed; final F-07 acceptance remains pending.

## F-07 — Product Owner Acceptance and Closeout

**Acceptance date:** 2026-11-26

**Disposition:** PASS WITH DOCUMENTED LIMITATIONS — LOCAL MVP DEVELOPMENT ONLY

**Accepted application revision:** `2dff0dbd499592428aa3a7c6ebfa5dfcc716b275`

On 2026-11-26, after T05 and the successful Product Owner Copilot recheck, the Product Owner explicitly accepted F-07 for local MVP development and authorized this documentation-only closeout. This decision covers the local development workflow. Production certification remains outside scope.

| Checkpoint | Acceptance evidence |
| --- | --- |
| T01 and SEC-02 | Dashboard and module navigation alignment reached main in PR #37. Next.js 16.4.6 is the accepted patch baseline. |
| T02C and T02D | Browser and automated evidence covers Documents upload and processing, owner isolation, CSRF, session persistence and logout, and My Credentials with protected Vault access. |
| T02E and T03A | The origin investigation verified the corrected dashboard. T03A established the permanent main development runtime. |
| T04 | The permanent API found an indexed candidate but withheld the citation because its storage root lacked the fixture artifacts. The negative fallback worked. |
| T05 and PO recheck | The protected store restored synthetic document access and the Version 1 reference in the permanent runtime. The unrelated question continued to show the insufficient-documentation fallback. The PO subsequently confirmed the Copilot recheck. |

### Retained limitations

- Copilot provides authorized references and a fallback. External generative AI and private-document transfer remain disabled. Private Web Documentation remains deferred.
- The temporary global-privilege exception for the local development MySQL account remains. Migration of historical artifacts other than the approved T05 synthetic fixture was outside scope.
- The historical citation wait timed out once and passed on a focused retry. Earlier browser-console messages were not retained individually, so exact attribution remains unavailable.
- The PO did not personally recheck five checklist items. The acceptance decision relies on prior automated evidence for those items. This record does not attribute individual personal checks to the PO beyond the confirmed Copilot recheck.
- Existing F-03, F-04, and F-05 limitations carry forward. F-05 operational Vault HOLDs, the destructive-purge HOLD, and the IC-024 account deletion deferral remain open or deferred as previously recorded.

### Permanent local development runtime

| Setting | Accepted local installation |
| --- | --- |
| Checkout | `C:/Users/dc/PycharmProjects/it_copilot_main_runtime` |
| Application source | `2dff0dbd499592428aa3a7c6ebfa5dfcc716b275` |
| Frontend | `http://127.0.0.1:3100` |
| API | `http://127.0.0.1:8100` |
| Database | `it_copilot_dev` on local MySQL |
| Protected development artifact store | `C:/Users/dc/PycharmProjects/it_copilot_dev_artifacts` |

Start local development services from the approved main-runtime checkout. The ignored configuration aligns the frontend API URL and Django browser origin, selects the development database, preserves the existing development Vault settings, and points Django to the protected artifact store. Use access-restricted local configuration and a private artifact directory outside served paths. The paths above record this installation. On another machine, choose local paths that meet the same requirements. A GitHub merge does not restart local services.

The permanent checkout's pre-existing `next-env.d.ts` diff redirects generated type imports to `.next/dev/types`, as expected when Next.js runs in development mode. It remains local runtime housekeeping and is excluded from the documentation publication.
