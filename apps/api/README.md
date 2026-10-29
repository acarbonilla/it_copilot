# Django API

IC-002 provides Django 5.2/DRF with native Windows MySQL configuration and one
unauthenticated endpoint: `GET /api/v1/health`.

## Windows 10 setup (native MySQL)

Use PowerShell from `apps/api`. Docker is not required.

1. Confirm the installed MySQL service and its actual port (for example with
   `Get-Service *mysql*` and MySQL Workbench or the service configuration).
2. Create a dedicated database and non-root development account. In a MySQL
   administrator session, adapt host names and passwords before running:

   ```sql
   CREATE DATABASE it_support_copilot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'it_copilot'@'localhost' IDENTIFIED BY 'choose-a-private-password';
   GRANT ALL PRIVILEGES ON it_support_copilot.* TO 'it_copilot'@'localhost';
   ```

3. Create and activate an environment, install dependencies, then create a
   private repository-root `.env` from `.env.example`:

   ```powershell
   py -3.13 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   Copy-Item ..\..\.env.example ..\..\.env
   ```

4. Set `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, and
   `MYSQL_PASSWORD` in `.env`. `MYSQL_HOST=127.0.0.1` avoids named-pipe/socket
   ambiguity, but only use port `3306` after confirming the local listener.
5. Review `docs/architecture/data-model.md`, then run `python manage.py check`,
   `python manage.py migrate --plan`, and `python manage.py migrate` twice.

MySQL connection, read, and write timeouts each default to five seconds and can
be changed with `MYSQL_CONNECT_TIMEOUT`, `MYSQL_READ_TIMEOUT`, and
`MYSQL_WRITE_TIMEOUT`. Values must be positive integers. Local MySQL settings
are the default; isolated tests use `config.settings.test`.

IC-003 configures `accounts.User` before enabling `django.contrib.auth`.
`django.contrib.admin` remains disabled. Create a development
superuser, if needed for backend verification, with:

```powershell
python manage.py createsuperuser
```

Email is the login identity; there is no username field. Application and IT
roles must be assigned separately.

## Local browser authentication

IC-004 uses `http://localhost:3000` for the frontend and
`http://localhost:8000` for this API. Browser clients use
`credentials: "include"`, bootstrap CSRF with `GET /api/v1/auth/csrf`, and send
the returned token as `X-CSRFToken` on login and logout. Django rotates the CSRF
secret during login, so refresh the bootstrap token before logout or another
unsafe request.

Local HTTP uses HttpOnly/Lax session cookies and a browser-readable/Lax CSRF
cookie. Set `DJANGO_COOKIE_SECURE=true` whenever the API is served over HTTPS;
the committed default `false` is an explicit local-development exception.

## Restricted local invitation mailbox

IC-006 invitation delivery is disabled by default. For a controlled local
development run only, set `DJANGO_DEBUG=true` and
`INVITATION_DELIVERY_MODE=file`. The API then creates one mode-`0600` JSON file
per invitation under the repository-ignored `tmp/invitations` directory by
default. The filename is the nonsecret invitation UUID returned by the invite
API; the file contains the recipient and local activation URL.

Only the developer operating the local environment may read this directory.
Do not serve, sync, commit, attach, log, or copy these files to shared storage.
Delete an artifact after its activation succeeds, and clear stale/revoked files
when the local verification session ends. Host filesystem ACLs remain the
operator's responsibility, especially on Windows where POSIX mode bits are not
an access-control boundary. Production-like runs must leave delivery disabled.

The database and filesystem do not share a distributed transaction. The service
removes a newly created artifact on write errors, transaction-body failures, and
caught database commit failures; a filename collision never removes the file it
found. A process or host crash after the write but before database commit can
still leave an orphan file. Such a token has no committed digest and cannot
activate an account, but the file remains sensitive local data and must be
removed by the documented end-of-session cleanup. Conversely, filesystem loss
after a successful database commit has no automatic redelivery mechanism.

