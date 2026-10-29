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
- Cross-owner and App Admin-only mutation denials: generic `PermissionDenied`; two controlled `authorization.denied` records containing only actor/target IDs and vocabulary fields.

## Commands

| Command | Result |
| --- | --- |
| `manage.py test documents --settings=config.settings.test -v 1` | PASS - authorization/service/constraint suite |
| `manage.py test documents -v 2` | PASS - 19/19 native MySQL |
| `manage.py test -v 1` | PASS - complete 142-test native MySQL backend regression |

No API, frontend, or browser route exists in Batch A; those enforcement surfaces remain mandatory later-batch G2 evidence.
