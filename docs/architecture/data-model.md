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

IC-003 must create its custom user application, set `AUTH_USER_MODEL`, and put
the user model in that application's `0001_initial` migration before enabling
or applying auth-related migrations on any shared or persistent database. If
that order cannot be maintained, migration work must stop and be escalated.

