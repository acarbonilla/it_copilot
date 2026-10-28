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

IC-004 enables Django's database session backend. Its only schema addition is
the framework-owned `django_session` table from `sessions.0001_initial`. The
sessions migration has no dependencies and does not alter `accounts_user`,
auth tables, or prior migration files. Session rows store server-side session
state; logout deletes the current row. Account deactivation blocks the next
authenticated request through a fresh user lookup but does not bulk-delete
historical rows, which remains IC-007 scope.

IC-008 adds the append-only `security_audit_securityauditevent` table. Each row
stores a controlled action, nullable positive actor user ID snapshot (not a
foreign key), controlled target type, optional constrained opaque target ID,
controlled outcome, occurrence timestamp, and optional constrained request
correlation ID. Database checks enforce action, target type, outcome, and actor
ID domains; indexes support action/time and actor/time review. The schema has no
metadata, email, IP address, credential, token, cookie, session identifier, raw
payload, or exception text column. No retention or cascade behavior is defined.

IC-006 adds `accounts_user.lifecycle_state`. Existing rows default to `ACTIVE`;
new invitees use `PENDING_INVITATION` together with `is_active=False` and an
unusable password until activation. This explicit marker prevents an existing
inactive account from being mistaken for a pending invite and silently
reactivated.

`accounts_accountinvitation` uses a UUID primary key, protected user foreign
key, unique 64-character SHA-256 token digest, creation/expiry/consumption/
revocation timestamps, and a positive immutable inviter user-ID snapshot. Raw
activation secrets and URLs are absent. A check prevents one row from being
both consumed and revoked; `(user, created_at)` supports invitation history.
IC-006 also extends the audit action/target constraints through the forward
`security_audit.0002_ic006_event_vocabulary` migration without altering the
applied IC-008 migration.

