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

