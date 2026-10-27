# IC-003 test results

**Status:** Task-branch verification complete; SOL review pending
**Environment:** Windows native MySQL 8.0, Python 3.13.5, Django 5.2.7

## Migration gate evidence

- Pre-migration native records: only `contenttypes.0001_initial` and
  `contenttypes.0002_remove_content_type_name`.
- Pre-migration native tables: only `django_content_type` and
  `django_migrations`.
- Private ignored pre-migration dump: created successfully (3,119 bytes).
- Fresh isolated migration: passed; repeat run reported no migrations.
- Isolated schema: `accounts_user` present and `auth_user` absent.
- Native migration: passed; repeat run reported no migrations; 15 total
  migration records.
- Native schema: `accounts_user` present and `auth_user` absent.
- Native email collation: `utf8mb4_0900_ai_ci`.
- Raw SQL case-only duplicate: rejected by unique index with MySQL error 1062;
  transaction rolled back and verification count was zero.

## Automated and regression results

| Check | Result |
| --- | --- |
| Django isolated system check | Passed, no issues |
| Fresh isolated migration | Passed |
| Second isolated migration | Passed; `No migrations to apply` |
| `migrate --check` | Passed on isolated and native databases |
| `makemigrations --check --dry-run` | Passed; no model drift |
| Full `accounts health` suite | Passed, 26/26 tests |
| Email canonicalization/login/password hashing | Passed |
| Case-insensitive duplicate rejection | Passed in automated suite and raw native MySQL constraint test |
| Active/inactive authentication | Passed |
| IT role action matrices | Passed |
| App Admin/superuser without IT role denial | Passed |
| Anonymous/disabled/unknown-role default denial | Passed |
| Cross-owner Web-document and vault denial | Passed for every role and admin flag combination |
| Custom-user migration graph tests | Passed |
| Native Django database check | Passed |
| IC-002 health regression | Passed; HTTP 200 and exact JSON body |
| IC-002 failure/renderer/timeout regressions | Passed as part of the 26-test suite |
| Repository validation | Passed |

## IC-003-REV-01

- Empty email authentication returns `None` without an exception.
- Whitespace-only email authentication returns `None` without an exception.
- Empty and whitespace-only account creation remain strictly rejected.
- Full `accounts health` suite: 29/29 tests passed.
- Fresh isolated migration passed; immediate repeat reported
  `No migrations to apply`; isolated `migrate --check` passed.
- `makemigrations --check --dry-run`: passed with no model drift.
- Native database system check and `migrate --check`: passed.
- Live IC-002 health regression: HTTP 200, `application/json`, exact body
  `{"status":"ok"}`.
- Repository validation and diff whitespace check: passed.

No credentials were printed or committed. The backup is under the ignored
`tmp/` directory and is not an off-machine disaster-recovery backup.
