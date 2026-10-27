# IC-003 implementation

**Status:** Ready for PR
**Branch:** `task/IC-003-custom-user-roles`  
**Target:** `feature/core-platform`  
**Authorization:** Product Owner approval of D-01 through D-05, 2026-10-27

## Scope implemented

- `accounts.User` uses `AbstractBaseUser` and `PermissionsMixin`, unique
  lowercase email identity, Django password hashing, and independent active,
  staff, superuser, App Admin, and IT-role fields.
- `UserManager` implements canonicalized `create_user`, `create_superuser`, and
  natural-key email lookup. Superuser creation does not assign App Admin or an
  IT role.
- IT roles are `NONE`, `IT_DOC_ADMIN`, `IT_EDITOR`, and `IT_MEMBER`, defaulting
  to `NONE`.
- Central policy helpers default deny and separately cover shared IT document
  actions, private Web documents, and credential vault ownership.
- No document/vault model, CRUD endpoint, UI, session login, or admin site was
  introduced.

## Migration safety

Before implementation, native MySQL contained only `django_migrations` and
`django_content_type`, with the two IC-002 contenttypes migrations applied.
No auth/default-user tables or migration records existed. An ignored private
pre-migration dump was created successfully.

`AUTH_USER_MODEL` was configured before auth was enabled. The custom user is
created in `accounts.0001_initial`; auth's default User operation is swappable
and produced no `auth_user` table. The graph was migrated twice on a fresh
isolated database before native MySQL migration.

Native migration then succeeded and repeated safely. MySQL confirmed a
case-insensitive email collation and rejected a raw case-only duplicate through
the unique index. No default-user table was created.
