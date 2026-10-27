# API documentation

IC-002 exposes exactly one route:

| Request | Condition | Response |
| --- | --- | --- |
| `GET /api/v1/health` | MySQL responds to bounded `SELECT 1` | `200 {"status":"ok"}` |
| `GET /api/v1/health` | Connection/check fails | `503 {"error":{"code":"database_unavailable","message":"Service temporarily unavailable"}}` |

The query is read-only and the driver connect timeout defaults to five seconds.
The endpoint is unauthenticated for local development and returns no database
diagnostics. Other API failures use
`{"error":{"code":"stable_machine_code","message":"safe message"}}`.

