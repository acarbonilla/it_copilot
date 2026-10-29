# Web application

IC-005 implements the Next.js App Router shell with TypeScript, Tailwind CSS,
shadcn/ui-style primitives, and Django session authentication.

## Windows setup

From `apps/web`:

```powershell
npm install
npm run dev
```

The frontend runs at `http://localhost:3000` and expects Django at
`http://localhost:8000`. Override the API origin only when required with
`NEXT_PUBLIC_API_BASE_URL`. Run `npm run typecheck`, `npm run lint`, `npm test`,
and `npm run build` before submitting changes. Never store passwords, session
identifiers, or CSRF values in browser storage.

## Activation-token boundary

F02-SEC-001 delivers links as `/activate#token=<secret>`. URL fragments are not
sent in HTTP requests or server-rendered props. The client reads and scrubs the
fragment before rendering the activation form, keeps the token only in memory,
and replaces the URL with `/login` after success. `Referrer-Policy: no-referrer`
provides defense in depth.

The former `/activate/[token]` route no longer exists. A request proxy returns a
constant token-free 404 response for legacy paths, and development request
logging ignores those paths to avoid reflecting old secrets. Do not place
activation tokens in browser storage, telemetry, audit records, or logs.

