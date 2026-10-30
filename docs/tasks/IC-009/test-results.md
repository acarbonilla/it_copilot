# IC-009 Test Results

**Environment:** Windows, Python virtual environment, Django 5.2.7, native MySQL local MVP database
**Executed during Batch A:** Yes

| Command/evidence | Result |
| --- | --- |
| `manage.py test documents --settings=config.settings.test -v 2` | PASS - 20 tests, one intentional MySQL-only skip |
| `manage.py test documents -v 2` | PASS - 20/20 on native MySQL, including concurrent stale-revision race and version-reference ownership |
| `manage.py migrate` | PASS - both document migrations and audit vocabulary migration applied |
| `manage.py migrate --check` | PASS |
| `manage.py makemigrations --check --dry-run` | PASS - no model drift |
| `manage.py showmigrations documents security_audit` | PASS - all required migrations applied |
| `manage.py test -v 1` | PASS - complete 143-test native MySQL backend suite |

## Executable evidence

- Database constraints reject duplicate version sequence, missing deletion timestamp, duplicate nonterminal jobs, and terminal jobs retaining the nonterminal slot.
- Two native-MySQL writers using revision 1 produce exactly one successful revision-2 update and one conflict.
- Stale revisions and invalid lifecycle transitions preserve the prior document and audit count.
- Injected audit database failure rolls back create and archive mutations.
- Create/update/archive/restore/delete produce the expected ordered controlled audit actions.
- Same-document current/candidate references save successfully; cross-document references for either field raise validation and leave persisted references unchanged.

Batch A contains no frontend or browser behavior, so frontend and Playwright suites are not applicable at this boundary.
