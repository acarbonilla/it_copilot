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
