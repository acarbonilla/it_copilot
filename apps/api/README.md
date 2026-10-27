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

