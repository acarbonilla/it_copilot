# API documentation

IC-002 exposes exactly one route:

| Request | Condition | Response |
| --- | --- | --- |
| `GET /api/v1/health` | MySQL responds to bounded `SELECT 1` | `200 {"status":"ok"}` |
| `GET /api/v1/health` | Connection/check fails | `503 {"error":{"code":"database_unavailable","message":"Service temporarily unavailable"}}` |

The query is read-only and the driver connection, read, and write timeouts each
default to five seconds.
The endpoint is unauthenticated for local development and returns no database
diagnostics. Other API failures use
`{"error":{"code":"stable_machine_code","message":"safe message"}}`.
All API responses use DRF's JSON renderer. An unacceptable media type such as
`Accept: text/html` receives a structured JSON `406` response rather than
invoking the browsable API template renderer.

## Session authentication

| Request | Success | Notes |
| --- | --- | --- |
| `GET /api/v1/auth/csrf` | `200 {"csrfToken":"..."}` | Anonymous bootstrap; sets the CSRF cookie |
| `POST /api/v1/auth/login` | `200 {"user":{...}}` | CSRF required; email/password; rotates session and CSRF secrets |
| `POST /api/v1/auth/logout` | `204` empty body | Authentication and current CSRF token required; deletes current session |
| `GET /api/v1/auth/me` | `200 {"user":{...}}` | Active authenticated session required |

The user payload contains only `id`, `email`, `is_app_admin`, and `it_role`.
Invalid credentials and inactive accounts share the same safe `401` response.
Missing sessions receive structured `401`; CSRF failures receive structured
`403` with code `csrf_failed`. The only credentialed browser origin is
`http://localhost:3000`; wildcard CORS is disabled.

