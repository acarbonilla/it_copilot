# IC-010 Test Results

**Environment:** Windows, Django 5.2.7, native MySQL local MVP database
**Executed during Batch A:** Yes

## Matrix evidence

- Owner `IT_MEMBER` and `IT_EDITOR`: own operations allowed, cross-owner denied.
- `IT_DOC_ADMIN`: cross-owner metadata/content/lifecycle allowed for non-deleted documents.
- App Admin only: operational metadata allowed; every content/lifecycle capability denied.
- Combined App Admin plus `IT_EDITOR`: own content allowed, cross-owner content denied, operational metadata allowed.
- Inactive/deactivated owner: denied immediately.
- Deleted document: denied even to `IT_DOC_ADMIN` through normal access policy.
- Querysets: owner scoped, `IT_DOC_ADMIN` organization-wide, App Admin-only empty, deleted excluded.
- Existing cross-owner, nonexistent UUID, deleted document, deactivated owner, and stale role-downgraded owner: identical `DocumentUnavailableError("Document is unavailable")` outcomes.
- All five unavailable attempts produce controlled `authorization.denied` records with `target_id = NULL`; restricted audit consumers cannot distinguish identifier existence from those records.

## Commands

| Command | Result |
| --- | --- |
| `manage.py test documents --settings=config.settings.test -v 2` | PASS - 20 tests; MySQL concurrency test intentionally skipped |
| `manage.py test documents -v 2` | PASS - 20/20 native MySQL |
| `manage.py test -v 1` | PASS - complete 143-test native MySQL backend regression |

No API, frontend, or browser route exists in Batch A; those enforcement surfaces remain mandatory later-batch G2 evidence.
