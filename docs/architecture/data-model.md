# Initial schema and migration dependencies

IC-002 intentionally owns no domain model. Its migration plan contains only:

1. Django creates the `django_migrations` bookkeeping table.
2. `contenttypes.0001_initial` creates `django_content_type`.
3. `contenttypes.0002_remove_content_type_name` adjusts that framework table.

The dependency graph is `contenttypes.0001_initial` →
`contenttypes.0002_remove_content_type_name`; neither migration depends on a
user model. `django.contrib.auth`, `django.contrib.admin`, and
`django.contrib.sessions` are deliberately not installed, so their migrations
must not be applied during IC-002.

IC-003 adds `accounts.User` in `accounts.0001_initial` and configures
`AUTH_USER_MODEL = "accounts.User"` before enabling auth migrations. The model
uses unique lowercase email identity, Django password hashes, active/staff/
superuser/App Admin flags, and one non-null IT role (`NONE`, `IT_DOC_ADMIN`,
`IT_EDITOR`, or `IT_MEMBER`). App Admin and framework flags remain independent
from the IT role.

`PermissionsMixin` references auth groups and permissions, so the generated
`accounts.0001_initial` depends on `auth.0012`. Django's `auth.0001` default
User operation is swappable and is skipped because `AUTH_USER_MODEL` already
selects `accounts.User`; verified isolated and native schemas contain no
`auth_user` table. The resulting order is existing contenttypes migrations,
auth permission/group migrations, then `accounts.0001_initial`.

Native MySQL uses the case-insensitive `utf8mb4_0900_ai_ci` collation for
`accounts_user.email` plus a unique index. A raw-SQL duplicate differing only
in case was rejected with MySQL error 1062 and rolled back.

